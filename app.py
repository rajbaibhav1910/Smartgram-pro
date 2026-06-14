from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
import boto3
from boto3.dynamodb.conditions import Attr
import uuid, hashlib, os
from datetime import datetime
from config import Config
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)

# AWS clients — uses IAM Role attached to EC2 (no hardcoded keys)
dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION'])
s3       = boto3.client('s3',         region_name=app.config['AWS_REGION'])
sns      = boto3.client('sns',        region_name=app.config['AWS_REGION'])

users_table      = dynamodb.Table(app.config['USERS_TABLE'])
complaints_table = dynamodb.Table(app.config['COMPLAINTS_TABLE'])
notices_table    = dynamodb.Table(app.config['NOTICES_TABLE'])

# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def gen_id(prefix):
    ts  = datetime.now().strftime('%Y%m%d%H%M%S')
    uid = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{ts}-{uid}"

def notify(subject, message):
    try:
        sns.publish(TopicArn=app.config['SNS_TOPIC_ARN'],
                    Subject=subject, Message=message)
    except Exception as e:
        app.logger.warning(f"SNS failed: {e}")

def upload_s3(file, filename):
    try:
        s3.upload_fileobj(file, app.config['S3_BUCKET'],
                          f"complaint-images/{filename}",
                          ExtraArgs={'ContentType': file.content_type})
        return (f"https://{app.config['S3_BUCKET']}.s3.amazonaws.com"
                f"/complaint-images/{filename}")
    except Exception as e:
        app.logger.error(f"S3 error: {e}")
        return None

def logged_in():  return 'user_id' in session
def is_admin():   return session.get('role') == 'admin'

# ── Error handlers ─────────────────────────────────────────────────────────────

@app.errorhandler(413)
def too_large(e):
    flash('File too large! Maximum size is 1 MB.', 'danger')
    return redirect(url_for('submit_complaint'))

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    try:
        total    = complaints_table.scan(Select='COUNT')['Count']
        resolved = complaints_table.scan(
            FilterExpression=Attr('status').eq('Resolved'),
            Select='COUNT')['Count']
        notices  = notices_table.scan(Select='COUNT')['Count']
    except:
        total = resolved = notices = 0
    return render_template('index.html',
                           complaints_count=total,
                           resolved=resolved,
                           notices_count=notices)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']
        village  = request.form['village'].strip()
        phone    = request.form['phone'].strip()
        role     = request.form.get('role', 'villager')

        if not all([username, email, password, village, phone]):
            flash('All fields are required!', 'danger')
            return render_template('register.html')

        existing = users_table.scan(
            FilterExpression=Attr('username').eq(username))
        if existing['Count'] > 0:
            flash('Username already taken.', 'warning')
            return render_template('register.html')

        users_table.put_item(Item={
            'user_id':       gen_id('USR'),
            'username':      username,
            'email':         email,
            'password_hash': hash_pw(password),
            'role':          role,
            'village':       village,
            'phone':         phone,
            'created_at':    datetime.now().isoformat()
        })
        flash('Registered successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        result = users_table.scan(
            FilterExpression=Attr('username').eq(username))
        if result['Count'] == 0:
            flash('User not found. Please register first.', 'danger')
            return render_template('login.html')

        user = result['Items'][0]
        if user['password_hash'] != hash_pw(password):
            flash('Incorrect password.', 'danger')
            return render_template('login.html')

        session.update({
            'user_id':  user['user_id'],
            'username': user['username'],
            'role':     user['role'],
            'village':  user['village'],
            'email':    user['email']
        })
        flash(f"Welcome, {user['username']}!", 'success')
        return redirect(url_for('admin_dashboard') if user['role'] == 'admin'
                        else url_for('dashboard'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    name = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {name}!', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if not logged_in():
        flash('Please login first.', 'warning')
        return redirect(url_for('login'))
    result = complaints_table.scan(
        FilterExpression=Attr('user_id').eq(session['user_id']))
    complaints = sorted(result['Items'],
                        key=lambda x: x['submitted_at'], reverse=True)
    return render_template('dashboard.html', complaints=complaints)


@app.route('/complaint', methods=['GET', 'POST'])
def submit_complaint():
    if not logged_in():
        flash('Please login to submit a complaint.', 'warning')
        return redirect(url_for('login'))

    categories = ['Road Damage', 'Water Supply', 'Electricity',
                  'Sanitation', 'School/Education', 'Health',
                  'Agriculture', 'Other']

    if request.method == 'POST':
        category    = request.form['category']
        description = request.form['description'].strip()

        if len(description) < 20:
            flash('Description must be at least 20 characters.', 'danger')
            return render_template('complaint.html', categories=categories)

        image_url = None
        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            fname     = secure_filename(file.filename)
            unique    = f"{gen_id('IMG')}_{fname}"
            image_url = upload_s3(file, unique)

        cid = gen_id('CMP')
        complaints_table.put_item(Item={
            'complaint_id':  cid,
            'user_id':       session['user_id'],
            'username':      session['username'],
            'email':         session['email'],
            'category':      category,
            'description':   description,
            'image_url':     image_url or '',
            'status':        'Pending',
            'village':       session['village'],
            'submitted_at':  datetime.now().isoformat(),
            'updated_at':    datetime.now().isoformat(),
            'admin_remarks': ''
        })

        notify(
            subject=f"New Complaint: {category} – {session['village']}",
            message=(f"Complaint ID: {cid}\n"
                     f"From: {session['username']} ({session['village']})\n"
                     f"Category: {category}\n"
                     f"Description: {description}\n"
                     f"Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        )

        flash(f'Complaint submitted! ID: {cid}', 'success')
        return redirect(url_for('dashboard'))

    return render_template('complaint.html', categories=categories)


@app.route('/admin')
def admin_dashboard():
    if not is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('login'))

    all_c = complaints_table.scan()['Items']
    total = len(all_c)
    cats  = {}
    for c in all_c:
        cats[c.get('category', 'Other')] = cats.get(c.get('category', 'Other'), 0) + 1

    return render_template('admin.html',
        complaints  = sorted(all_c, key=lambda x: x['submitted_at'], reverse=True),
        total       = total,
        pending     = sum(1 for c in all_c if c['status'] == 'Pending'),
        in_progress = sum(1 for c in all_c if c['status'] == 'In Progress'),
        resolved    = sum(1 for c in all_c if c['status'] == 'Resolved'),
        categories  = cats)


@app.route('/admin/update_status', methods=['POST'])
def update_status():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403

    cid     = request.form['complaint_id']
    status  = request.form['status']
    remarks = request.form.get('remarks', '')

    complaints_table.update_item(
        Key={'complaint_id': cid},
        UpdateExpression='SET #st = :s, admin_remarks = :r, updated_at = :u',
        ExpressionAttributeNames={'#st': 'status'},
        ExpressionAttributeValues={
            ':s': status, ':r': remarks,
            ':u': datetime.now().isoformat()
        }
    )

    c = complaints_table.get_item(Key={'complaint_id': cid}).get('Item', {})
    notify(
        subject=f"Complaint {cid} Updated – {status}",
        message=(f"Your complaint status has changed.\n"
                 f"ID: {cid}\nCategory: {c.get('category')}\n"
                 f"New Status: {status}\nRemarks: {remarks}")
    )

    flash(f'Status updated to {status}', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/post_notice', methods=['POST'])
def post_notice():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403

    notices_table.put_item(Item={
        'notice_id':   gen_id('NTC'),
        'title':       request.form['title'],
        'content':     request.form['content'],
        'category':    request.form['category'],
        'posted_by':   session['username'],
        'posted_at':   datetime.now().isoformat(),
        'expiry_date': request.form.get('expiry_date', '')
    })
    flash('Notice posted!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/notices')
def notices():
    all_n = notices_table.scan()['Items']
    all_n = sorted(all_n, key=lambda x: x['posted_at'], reverse=True)
    return render_template('notices.html', notices=all_n)


@app.route('/schemes')
def schemes():
    schemes_data = [
        {'name': 'PM Awas Yojana (PMAY)',
         'description': 'Financial assistance to build pucca houses for rural families.',
         'benefit': 'Up to ₹1.2 lakh assistance', 'eligibility': 'BPL families without pucca house',
         'link': 'https://pmaymis.gov.in'},
        {'name': 'PM Kisan Samman Nidhi',
         'description': 'Direct income support of ₹6,000/year to farmer families.',
         'benefit': '₹6,000/year in 3 installments', 'eligibility': 'Farmers with < 2 hectares land',
         'link': 'https://pmkisan.gov.in'},
        {'name': 'Jal Jeevan Mission',
         'description': 'Tap water connection to every rural household.',
         'benefit': 'Free tap water connection', 'eligibility': 'Rural households without tap',
         'link': 'https://jaljeevanmission.gov.in'},
        {'name': 'PM Ujjwala Yojana',
         'description': 'Free LPG connection to BPL families.',
         'benefit': 'Free cylinder + connection', 'eligibility': 'BPL women without LPG',
         'link': 'https://pmuy.gov.in'},
        {'name': 'MGNREGA',
         'description': '100 days guaranteed employment per year to rural households.',
         'benefit': '100 days of work at minimum wage', 'eligibility': 'Any rural adult',
         'link': 'https://nrega.nic.in'},
    ]
    return render_template('schemes.html', schemes=schemes_data)


@app.route('/api/stats')
def api_stats():
    c = complaints_table.scan()['Items']
    return jsonify({
        'total':       len(c),
        'pending':     sum(1 for x in c if x['status'] == 'Pending'),
        'in_progress': sum(1 for x in c if x['status'] == 'In Progress'),
        'resolved':    sum(1 for x in c if x['status'] == 'Resolved'),
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
