# lambda/pending_reminder.py
# AWS Lambda function — runs daily via EventBridge
# Scans DynamoDB for pending complaints → sends SNS summary email

import boto3
import os
from datetime import datetime

# AWS clients (Lambda automatically uses its IAM Role)
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns      = boto3.client('sns',      region_name='us-east-1')

TABLE_NAME    = os.environ.get('TABLE_NAME',    'SmartGramComplaints')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:YOUR_ACCOUNT:SmartGramAlerts')

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)

    # Scan for all Pending complaints
    result = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('status').eq('Pending')
    )
    pending = result.get('Items', [])
    count   = len(pending)

    # Build email body
    today = datetime.now().strftime('%Y-%m-%d')
    if count == 0:
        subject = f"SmartGram Pro: No Pending Complaints on {today}"
        body    = f"Great news! All complaints have been addressed as of {today}."
    else:
        lines = [f"SmartGram Pro – Daily Pending Complaints Report ({today})",
                 f"Total Pending: {count}\n",
                 "Complaint Details:"]
        for c in pending:
            lines.append(
                f"  • {c.get('complaint_id')} | {c.get('category')} | "
                f"{c.get('village')} | Filed: {str(c.get('submitted_at',''))[:10]}"
            )
        lines.append("\nPlease login to the SmartGram Pro admin panel to take action.")
        body    = '\n'.join(lines)
        subject = f"SmartGram Pro: {count} Complaint(s) Still Pending – Action Required"

    # Publish to SNS
    sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=body)

    print(f"[Lambda] {today} – Sent reminder for {count} pending complaints")
    return {'statusCode': 200, 'body': f'{count} pending complaints notified'}
