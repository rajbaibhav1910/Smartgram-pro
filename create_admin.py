"""
create_admin.py
Run ONCE on EC2 to seed the default admin account.
Usage: python3 create_admin.py
"""
import boto3, hashlib
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table    = dynamodb.Table('SmartGramUsers')

table.put_item(Item={
    'user_id':       'USR-ADMIN-001',
    'username':      'admin',
    'email':         'admin@smartgram.gov.in',
    'password_hash': hashlib.sha256('admin123'.encode()).hexdigest(),
    'role':          'admin',
    'village':       'All Villages',
    'phone':         '9999999999',
    'created_at':    datetime.now().isoformat()
})
print("✅ Admin user created!")
print("   Username: admin")
print("   Password: admin123")
print("   Change the password after first login!")
