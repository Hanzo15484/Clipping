import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    
    # Roles
    STAFF_ROLE = os.getenv('STAFF_ROLE', 'Staff')
    ADMIN_ROLE = os.getenv('ADMIN_ROLE', 'Admin')
    
    # Channels
    LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', '0'))
    SUBMISSION_CHANNEL_ID = int(os.getenv('SUBMISSION_CHANNEL_ID', '0'))
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.sqlite')
    
    # Tracking
    TRACKING_INTERVAL_MINUTES = int(os.getenv('TRACKING_INTERVAL_MINUTES', '30'))
    CLEANUP_INTERVAL_HOURS = int(os.getenv('CLEANUP_INTERVAL_HOURS', '24'))
    
    # Validation
    USDT_WALLET_REGEX = r'^0x[a-fA-F0-9]{40}$'
    
    # Platforms
    PLATFORMS = ['instagram', 'tiktok', 'youtube']
    
    # Statuses
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_BANNED = 'banned'
    STATUS_LIVE = 'live'
    STATUS_ENDED = 'ended'
    STATUS_PAID = 'paid'
    STATUS_PROCESSING = 'processing'
