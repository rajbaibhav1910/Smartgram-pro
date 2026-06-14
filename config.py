# config.py — SmartGram Pro Production Configuration
import os

class Config:
    SECRET_KEY       = os.environ.get('SECRET_KEY', 'smartgram-rajbaibhav-secret-2024')
    AWS_REGION       = 'us-east-1'

    # S3 Bucket for complaint images
    S3_BUCKET        = 'smartgram-pro-images-rajbaibhav'

    # DynamoDB Table Names
    USERS_TABLE      = 'SmartGramUsers'
    COMPLAINTS_TABLE = 'SmartGramComplaints'
    NOTICES_TABLE    = 'SmartGramNotices'

    # SNS Topic ARN for email alerts
    SNS_TOPIC_ARN    = 'arn:aws:sns:us-east-1:070490636986:SmartGramAlerts'

    MAX_CONTENT_LENGTH = 1 * 1024 * 1024   # 1 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
