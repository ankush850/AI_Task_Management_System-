import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'JARM')
    # Generate a secure random password if not provided
    DB_PASSWORD = os.getenv('DB_PASSWORD') or secrets.token_urlsafe(32)
    DB_NAME = os.getenv('DB_NAME', 'task_management')

    # Flask Configuration
    # Generate a secure random secret key if not provided
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_urlsafe(32)
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'  # Default to False for security

    # Monitoring Configuration
    CPU_THRESHOLD = float(os.getenv('CPU_THRESHOLD', 80.0))
    MEMORY_THRESHOLD = float(os.getenv('MEMORY_THRESHOLD', 85.0))
    ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', 300))  # 5 minutes
    
    # Timeout Configuration
    MONITORING_TIMEOUT = int(os.getenv('MONITORING_TIMEOUT', 30))  # seconds
    DATABASE_TIMEOUT = int(os.getenv('DATABASE_TIMEOUT', 20))  # seconds
    API_REQUEST_TIMEOUT = int(os.getenv('API_REQUEST_TIMEOUT', 15))  # seconds

    # Learning Configuration
    Q_LEARNING_ALPHA = float(os.getenv('Q_LEARNING_ALPHA', 0.1))
    Q_LEARNING_GAMMA = float(os.getenv('Q_LEARNING_GAMMA', 0.9))
    Q_LEARNING_EPSILON = float(os.getenv('Q_LEARNING_EPSILON', 0.1))

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'system_monitor.log')
    ALERT_LOG_FILE = os.getenv('ALERT_LOG_FILE', 'system_alerts.log')

    # Security Configuration
    MAX_TASK_SIZE = int(os.getenv('MAX_TASK_SIZE', 1000000))  # 1MB
    SUSPICIOUS_PATTERNS = [
        'rm -rf',
        'format',
        'del /f',
        'shutdown',
        'reboot',
        'killall',
        'taskkill'
    ]

    @classmethod
    def get_db_url(cls):
        """Get database URL for SQLAlchemy with proper escaping"""
        import urllib.parse
        password = urllib.parse.quote_plus(cls.DB_PASSWORD)
        return f"mysql+pymysql://{cls.DB_USER}:{password}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def validate_config(cls):
        """Validate configuration values"""
        if not cls.DB_HOST:
            raise ValueError("DB_HOST is required")
        if not cls.DB_USER:
            raise ValueError("DB_USER is required")
        if not cls.DB_NAME:
            raise ValueError("DB_NAME is required")
        if cls.DEBUG:
            print("WARNING: Debug mode is enabled. This should be disabled in production.")
        return True
