import os

class Config:
    # Database: Use Cloud DB if available, else local fallback
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///local_test.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key_fallback_123'
    
    # AWS S3 Config
    S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
    S3_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
    S3_SECRET = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_REGION = os.environ.get('AWS_REGION', 'us-east-1')