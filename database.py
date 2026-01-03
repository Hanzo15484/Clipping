import sqlite3
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """Connect to database"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
        return self.connection
        
    def ensure_connected(self):
        """Ensure database is connected"""
        if self.connection is None:
            self.connect()
        
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            
    def initialize(self):
        """Initialize database with all tables"""
        self.ensure_connected()
        
        try:
            # Users table
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    usdt_wallet TEXT,
                    total_earnings REAL DEFAULT 0,
                    paid_earnings REAL DEFAULT 0,
                    pending_earnings REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Social profiles
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS social_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    profile_url TEXT NOT NULL,
                    normalized_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    followers INTEGER DEFAULT 0,
                    tier TEXT,
                    verified_at TIMESTAMP,
                    verified_by TEXT,
                    rejection_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_id),
                    FOREIGN KEY(discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
                )
            ''')
            
            # Banned profiles
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS banned_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    profile_url TEXT NOT NULL,
                    normalized_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    banned_by TEXT NOT NULL,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_id)
                )
            ''')
            
            # Campaigns
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    total_budget REAL NOT NULL,
                    rate_per_100k REAL NOT NULL,
                    rate_per_1m REAL NOT NULL,
                    min_views INTEGER NOT NULL,
                    min_followers INTEGER NOT NULL,
                    max_earn_per_creator REAL NOT NULL,
                    max_earn_per_post REAL NOT NULL,
                    status TEXT DEFAULT 'live',
                    created_by TEXT NOT NULL,
                    ended_at TIMESTAMP,
                    remaining_budget REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Submissions
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    social_profile_id INTEGER NOT NULL,
                    video_url TEXT NOT NULL,
                    normalized_video_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    starting_views INTEGER NOT NULL,
                    current_views INTEGER DEFAULT 0,
                    earnings REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    tracking BOOLEAN DEFAULT FALSE,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP,
                    approved_by TEXT,
                    message_id TEXT,
                    UNIQUE(video_url),
                    UNIQUE(normalized_video_id),
                    FOREIGN KEY(discord_id) REFERENCES users(discord_id),
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                    FOREIGN KEY(social_profile_id) REFERENCES social_profiles(id)
                )
            ''')
            
            # Payouts
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS payouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    usdt_tx_hash TEXT,
                    paid_by TEXT,
                    paid_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(discord_id) REFERENCES users(discord_id),
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                )
            ''')
            
            # Activity logs
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    performed_by TEXT NOT NULL,
                    target_user TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # View tracking history
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS view_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    views INTEGER NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(submission_id) REFERENCES submissions(id)
                )
            ''')
            
            self.connection.commit()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
            
    def execute(self, query: str, params: tuple = ()):
        """Execute a query"""
        self.ensure_connected()
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor
        
    def fetch_one(self, query: str, params: tuple = ()):
        """Fetch single row"""
        self.ensure_connected()
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
        
    def fetch_all(self, query: str, params: tuple = ()):
        """Fetch all rows"""
        self.ensure_connected()
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
        
    def get_lastrowid(self):
        """Get last inserted row ID"""
        self.ensure_connected()
        return self.connection.cursor().lastrowid
