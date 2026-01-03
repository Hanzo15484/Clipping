import os
import asyncio
import sqlite3
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
STAFF_ROLE = os.getenv('STAFF_ROLE', 'Staff')
ADMIN_ROLE = os.getenv('ADMIN_ROLE', 'Admin')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', '0'))
SUBMISSION_CHANNEL_ID = int(os.getenv('SUBMISSION_CHANNEL_ID', '0'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.sqlite')

class Platform(Enum):
    INSTAGRAM = 'instagram'
    TIKTOK = 'tiktok'
    YOUTUBE = 'youtube'

class Status(Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    BANNED = 'banned'
    LIVE = 'live'
    ENDED = 'ended'
    PAID = 'paid'
    PROCESSING = 'processing'

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database with all tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # Users table
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS view_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    views INTEGER NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(submission_id) REFERENCES submissions(id)
                )
            ''')
            
            conn.commit()

class CLBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db = Database(DATABASE_PATH)
        self.log_channel = None
        self.submission_channel = None
        
    async def setup_hook(self):
        """Setup the bot after login"""
        await self.load_cogs()
        await self.sync_commands()
        
        # Start background tasks
        self.track_views.start()
        self.cleanup_data.start()
    
    async def load_cogs(self):
        """Load all cogs"""
        await self.add_cog(Commands(self))
        await self.add_cog(Events(self))
    
    async def sync_commands(self):
        """Sync slash commands"""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def log_action(self, action_type: str, performed_by: str, 
                        target_user: Optional[str] = None, details: Dict = None):
        """Log an action to database and Discord channel"""
        # Log to database
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute(
                "INSERT INTO activity_logs (action_type, performed_by, target_user, details) VALUES (?, ?, ?, ?)",
                (action_type, performed_by, target_user, json.dumps(details) if details else None)
            )
            conn.commit()
        
        # Log to Discord channel
        if self.log_channel:
            try:
                embed = discord.Embed(
                    title=f"📝 {action_type}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if performed_by != 'system':
                    embed.description = f"Action performed by <@{performed_by}>"
                
                if details:
                    embed.add_field(
                        name="Details",
                        value=f"```json\n{json.dumps(details, indent=2)}\n```",
                        inline=False
                    )
                
                await self.log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send log to channel: {e}")
    
    def normalize_profile_id(self, platform: str, url: str) -> Optional[str]:
        """Normalize social media profile URL to unique ID"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            match = re.search(r'instagram\.com/([^/?]+)', url)
            return f"ig:{match.group(1)}" if match else None
        elif platform == Platform.TIKTOK.value:
            match = re.search(r'tiktok\.com/@([^/?]+)', url)
            return f"tt:{match.group(1)}" if match else None
        elif platform == Platform.YOUTUBE.value:
            match = re.search(r'(?:youtube\.com/(?:c/|channel/|@)|youtu\.be/)([^/?]+)', url)
            return f"yt:{match.group(1)}" if match else None
        
        return None
    
    def normalize_video_id(self, platform: str, url: str) -> Optional[str]:
        """Normalize video URL to unique ID"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            match = re.search(r'instagram\.com/(?:reel|p)/([^/?]+)', url)
            return f"ig_video:{match.group(1)}" if match else None
        elif platform == Platform.TIKTOK.value:
            match = re.search(r'tiktok\.com/@[^/]+/video/(\d+)', url)
            return f"tt_video:{match.group(1)}" if match else None
        elif platform == Platform.YOUTUBE.value:
            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&?]+)', url)
            return f"yt_video:{match.group(1)}" if match else None
        
        return None
    
    async def check_permission(self, interaction: discord.Interaction, required_role: str) -> bool:
        """Check if user has required permissions"""
        member = interaction.user
        
        if required_role == 'user':
            return True
        
        if required_role == 'staff':
            return any(role.name in [STAFF_ROLE, ADMIN_ROLE] for role in member.roles)
        
        if required_role == 'admin':
            return any(role.name == ADMIN_ROLE for role in member.roles)
        
        return False
    
    async def enforce_permission(self, interaction: discord.Interaction, required_role: str) -> bool:
        """Enforce permission check and respond if failed"""
        has_perm = await self.check_permission(interaction, required_role)
        if not has_perm:
            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )
        return has_perm
    
    @tasks.loop(minutes=30)
    async def track_views(self):
        """Background task to track video views"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT s.*, c.rate_per_100k, c.rate_per_1m, 
                           c.max_earn_per_post, c.remaining_budget,
                           sp.status as profile_status
                    FROM submissions s
                    JOIN campaigns c ON s.campaign_id = c.id
                    JOIN social_profiles sp ON s.social_profile_id = sp.id
                    WHERE s.tracking = 1 
                      AND s.status = 'approved'
                      AND c.status = 'live'
                      AND sp.status != 'banned'
                ''')
                
                submissions = cursor.fetchall()
                
                for submission in submissions:
                    # Check stop conditions
                    if submission[21] <= 0:  # remaining_budget
                        conn.execute(
                            "UPDATE submissions SET tracking = FALSE WHERE id = ?",
                            (submission[0],)
                        )
                        continue
                    
                    # Get current views (mock implementation)
                    current_views = await self.get_video_views(submission[4], submission[6])  # video_url, platform
                    if current_views is None:
                        continue
                    
                    view_increase = current_views - submission[8]  # current_views
                    if view_increase <= 0:
                        continue
                    
                    # Calculate earnings
                    earnings = self.calculate_earnings(
                        view_increase,
                        submission[22],  # rate_per_100k
                        submission[23],  # rate_per_1m
                        submission[24] - submission[9]  # max_earn_per_post - earnings
                    )
                    
                    if earnings <= 0:
                        continue
                    
                    # Check campaign budget
                    if earnings > submission[21]:  # remaining_budget
                        conn.execute(
                            "UPDATE campaigns SET remaining_budget = 0 WHERE id = ?",
                            (submission[2],)  # campaign_id
                        )
                        conn.execute(
                            "UPDATE submissions SET tracking = FALSE WHERE id = ?",
                            (submission[0],)
                        )
                        continue
                    
                    # Update records
                    conn.execute('''
                        UPDATE submissions 
                        SET current_views = ?, 
                            earnings = earnings + ?,
                            tracking = CASE 
                                WHEN earnings + ? >= ? THEN FALSE 
                                ELSE tracking 
                            END
                        WHERE id = ?
                    ''', (current_views, earnings, earnings, submission[24], submission[0]))
                    
                    conn.execute(
                        "UPDATE campaigns SET remaining_budget = remaining_budget - ? WHERE id = ?",
                        (earnings, submission[2])
                    )
                    
                    conn.execute('''
                        UPDATE users 
                        SET total_earnings = total_earnings + ?,
                            pending_earnings = pending_earnings + ?
                        WHERE discord_id = ?
                    ''', (earnings, earnings, submission[1]))
                    
                    # Log view history
                    conn.execute(
                        "INSERT INTO view_history (submission_id, views) VALUES (?, ?)",
                        (submission[0], current_views)
                    )
                    
                    # Log milestone
                    if current_views >= 100000 or current_views % 10000 == 0:
                        await self.log_action(
                            'VIEW_MILESTONE',
                            'system',
                            submission[1],  # discord_id
                            {
                                'submission_id': submission[0],
                                'views': current_views,
                                'earnings': earnings
                            }
                        )
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"View tracking error: {e}")
            await self.log_action('TRACKING_ERROR', 'system', details={'error': str(e)})
    
    def calculate_earnings(self, views: int, rate_100k: float, rate_1m: float, max_earn: float) -> float:
        """Calculate earnings based on views and rates"""
        earnings_per_100k = (views / 100000) * rate_100k
        earnings_per_1m = (views / 1000000) * rate_1m
        earnings = max(earnings_per_100k, earnings_per_1m)
        return min(earnings, max_earn)
    
    async def get_video_views(self, url: str, platform: str) -> Optional[int]:
        """Mock function to get video views"""
        # In production, implement actual API calls
        import random
        return random.randint(1000, 10000)
    
    @tasks.loop(hours=24)
    async def cleanup_data(self):
        """Clean up old data"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                # Archive old logs (keep 90 days)
                conn.execute(
                    "DELETE FROM activity_logs WHERE timestamp < datetime('now', '-90 days')"
                )
                
                # Archive view history (keep 60 days)
                conn.execute(
                    "DELETE FROM view_history WHERE recorded_at < datetime('now', '-60 days')"
                )
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

class Commands(commands.Cog):
    def __init__(self, bot: CLBot):
        self.bot = bot
    
    # User Commands
@app_commands.command(name="my-profile", description="View your profile information")
  async def my_profile(self, interaction: discord.Interaction):
        """Display user profile"""
        if not await self.bot.enforce_permission(interaction, 'user'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Get user data
                cursor = conn.execute('''
                    SELECT u.*, 
                           COUNT(DISTINCT s.id) as total_submissions,
                           COUNT(DISTINCT CASE WHEN s.status = 'approved' THEN s.id END) as approved_submissions,
                           SUM(s.earnings) as total_earned
                    FROM users u
                    LEFT JOIN social_profiles sp ON u.discord_id = sp.discord_id
                    LEFT JOIN submissions s ON u.discord_id = s.discord_id
                    WHERE u.discord_id = ?
                ''', (str(interaction.user.id),))
                
                user = cursor.fetchone()
                
                if not user:
                    await interaction.followup.send(
                        "❌ You are not registered in the system.",
                        ephemeral=True
                    )
                    return
                
                # Get social profiles
                cursor = conn.execute('''
                    SELECT platform, profile_url, status, followers, verified_at
                    FROM social_profiles
                    WHERE discord_id = ?
                    ORDER BY platform, created_at
                ''', (str(interaction.user.id),))
                
                profiles = cursor.fetchall()
                
                # Create embed
                embed = discord.Embed(
                    title="👤 Your Profile",
                    description=f"Discord: <@{interaction.user.id}>",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📊 Statistics",
                    value=f"Submissions: {user[7] or 0}\nApproved: {user[8] or 0}\nTotal Earned: ${(user[9] or 0):.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="💰 Earnings",
                    value=f"Paid: ${user[4] or 0:.2f}\nPending: ${user[5] or 0:.2f}\nTotal: ${user[3] or 0:.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="💳 Wallet",
                    value=f"`{user[2]}`" if user[2] else "Not set",
                    inline=False
                )
                
                if profiles:
                    profile_text = "\n".join([
                        f"**{p[0].upper()}**: {p[1]}\nStatus: {p[2]} | Followers: {p[3]:,}"
                        for p in profiles
                    ])
                    embed.add_field(name="📱 Social Profiles", value=profile_text, inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in my_profile: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your profile.",
                ephemeral=True
            )
    
    @app_commands.command(name="my-stats", description="View your statistics and earnings")
    async def my_stats(self, interaction: discord.Interaction):
        """Display user statistics"""
        if not await self.bot.enforce_permission(interaction, 'user'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT 
                        COUNT(DISTINCT s.id) as total_submissions,
                        COUNT(DISTINCT CASE WHEN s.status = 'approved' THEN s.id END) as approved_submissions,
                        COUNT(DISTINCT s.campaign_id) as campaigns_participated,
                        SUM(s.current_views) as total_views,
                        SUM(s.earnings) as total_earned,
                        MAX(s.submitted_at) as last_submission
                    FROM submissions s
                    WHERE s.discord_id = ?
                ''', (str(interaction.user.id),))
                
                stats = cursor.fetchone()
                
                # Get active campaigns
                cursor = conn.execute('''
                    SELECT DISTINCT c.name, s.status
                    FROM submissions s
                    JOIN campaigns c ON s.campaign_id = c.id
                    WHERE s.discord_id = ? AND c.status = 'live' AND s.status = 'approved'
                ''', (str(interaction.user.id),))
                
                active_campaigns = cursor.fetchall()
                
                embed = discord.Embed(
                    title="📊 Your Statistics",
                    description=f"<@{interaction.user.id}>",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📤 Submissions",
                    value=f"Total: {stats[0] or 0}\nApproved: {stats[1] or 0}",
                    inline=True
                )
                
                embed.add_field(
                    name="👁️ Views",
                    value=f"{(stats[3] or 0):,}",
                    inline=True
                )
                
                embed.add_field(
                    name="💰 Earnings",
                    value=f"${(stats[4] or 0):.2f}",
                    inline=True
                )
                
                embed.add_field(
                    name="🎯 Campaigns",
                    value=f"{stats[2] or 0} participated",
                    inline=False
                )
                
                if stats[5]:  # last_submission
                    last_sub = datetime.fromisoformat(stats[5])
                    embed.add_field(
                        name="⏰ Last Submission",
                        value=f"<t:{int(last_sub.timestamp())}:R>",
                        inline=True
                    )
                
                if active_campaigns:
                    campaign_text = ", ".join([c[0] for c in active_campaigns])
                    embed.add_field(name="Active Campaigns", value=campaign_text)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in my_stats: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your statistics.",
                ephemeral=True
            )
    
    @app_commands.command(name="submit", description="Submit a video for a campaign")
    @app_commands.describe(
        campaign="Select campaign",
        profile="Select approved profile",
        video_url="Video link"
    )
    async def submit(self, interaction: discord.Interaction, campaign: str, profile: str, video_url: str):
        """Submit a video for approval"""
        if not await self.bot.enforce_permission(interaction, 'user'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Check if user exists
                cursor = conn.execute(
                    "SELECT * FROM users WHERE discord_id = ?",
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if not user:
                    await interaction.followup.send(
                        "❌ You must be registered first. Contact staff.",
                        ephemeral=True
                    )
                    return
                
                # Check campaign
                cursor = conn.execute(
                    "SELECT * FROM campaigns WHERE name = ? AND status = 'live'",
                    (campaign,)
                )
                campaign_data = cursor.fetchone()
                
                if not campaign_data:
                    await interaction.followup.send(
                        "❌ Campaign not found or not live.",
                        ephemeral=True
                    )
                    return
                
                # Check profile
                cursor = conn.execute('''
                    SELECT * FROM social_profiles 
                    WHERE discord_id = ? AND profile_url = ? AND status = 'approved'
                ''', (user_id, profile))
                
                profile_data = cursor.fetchone()
                
                if not profile_data:
                    await interaction.followup.send(
                        "❌ Profile not found or not approved.",
                        ephemeral=True
                    )
                    return
                
                # Check duplicate video
                normalized_video_id = self.bot.normalize_video_id(profile_data[2], video_url)
                if not normalized_video_id:
                    await interaction.followup.send(
                        "❌ Invalid video URL for this platform.",
                        ephemeral=True
                    )
                    return
                
                cursor = conn.execute(
                    "SELECT * FROM submissions WHERE normalized_video_id = ?",
                    (normalized_video_id,)
                )
                
                if cursor.fetchone():
                    await interaction.followup.send(
                        "❌ This video has already been submitted.",
                        ephemeral=True
                    )
                    return
                
                # Get starting views (mock)
                starting_views = await self.bot.get_video_views(video_url, profile_data[2])
                
                # Create submission
                cursor = conn.execute('''
                    INSERT INTO submissions 
                    (discord_id, campaign_id, social_profile_id, video_url, normalized_video_id, 
                     platform, starting_views, current_views)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    campaign_data[0],
                    profile_data[0],
                    video_url,
                    normalized_video_id,
                    profile_data[2],
                    starting_views,
                    starting_views
                ))
                
                submission_id = cursor.lastrowid
                conn.commit()
                
                # Post to submission channel
                if self.bot.submission_channel:
                    try:
                        embed = discord.Embed(
                            title="📤 New Submission",
                            color=discord.Color.orange(),
                            timestamp=datetime.now()
                        )
                        
                        embed.description = f"**Campaign:** {campaign_data[1]}\n**Platform:** {profile_data[2]}\n**Video:** {video_url}"
                        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
                        embed.add_field(name="Profile", value=profile, inline=True)
                        embed.add_field(name="Starting Views", value=f"{starting_views:,}", inline=True)
                        embed.add_field(name="Submission ID", value=f"#{submission_id}", inline=True)
                        
                        # Create buttons
                        view = discord.ui.View(timeout=None)
                        view.add_item(discord.ui.Button(
                            custom_id=f"approve_submission:{submission_id}",
                            label="✅ Approve",
                            style=discord.ButtonStyle.success
                        ))
                        view.add_item(discord.ui.Button(
                            custom_id=f"reject_submission:{submission_id}",
                            label="❌ Reject",
                            style=discord.ButtonStyle.danger
                        ))
                        view.add_item(discord.ui.Button(
                            custom_id=f"ban_profile:{profile_data[0]}",
                            label="🚫 Ban Profile",
                            style=discord.ButtonStyle.secondary
                        ))
                        
                        message = await self.bot.submission_channel.send(
                            content=f"<@&{ADMIN_ROLE}> New submission!",
                            embed=embed,
                            view=view
                        )
                        
                        # Update submission with message ID
                        conn.execute(
                            "UPDATE submissions SET message_id = ? WHERE id = ?",
                            (str(message.id), submission_id)
                        )
                        conn.commit()
                        
                    except Exception as e:
                        logger.error(f"Failed to post to submission channel: {e}")
                
                await interaction.followup.send(
                    "✅ Submission received! Staff will review it shortly.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'SUBMISSION_CREATED',
                    user_id,
                    details={
                        'submission_id': submission_id,
                        'campaign': campaign_data[1],
                        'video_url': video_url
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in submit: {e}")
            await interaction.followup.send(
                "❌ An error occurred while submitting.",
                ephemeral=True
              )
          @app_commands.command(name="add-payment", description="Add/update your USDT wallet address")
    @app_commands.describe(wallet="Your USDT (ERC20) wallet address")
    async def add_payment(self, interaction: discord.Interaction, wallet: str):
        """Add or update USDT wallet"""
        if not await self.bot.enforce_permission(interaction, 'user'):
            return
        
        # Validate USDT ERC20 address
        if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet):
            await interaction.response.send_message(
                "❌ Invalid USDT (ERC20) wallet address.",
                ephemeral=True
            )
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO users (discord_id, username, usdt_wallet)
                    VALUES (?, ?, ?)
                ''', (str(interaction.user.id), str(interaction.user), wallet))
                conn.commit()
            
            await interaction.response.send_message(
                f"✅ Wallet updated: `{wallet}`",
                ephemeral=True
            )
            
            await self.bot.log_action(
                'WALLET_UPDATED',
                str(interaction.user.id),
                details={'wallet': wallet}
            )
            
        except Exception as e:
            logger.error(f"Error in add_payment: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while updating wallet.",
                ephemeral=True
            )
    
    # Staff/Admin Commands
    
    @app_commands.command(name="register", description="[Staff] Register a social profile for user")
    @app_commands.describe(
        user="Discord user",
        platform="Platform",
        profile_url="Social profile link"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Instagram", value="instagram"),
        app_commands.Choice(name="TikTok", value="tiktok"),
        app_commands.Choice(name="YouTube", value="youtube")
    ])
    async def register(self, interaction: discord.Interaction, 
                      user: discord.User, platform: str, profile_url: str):
        """Register a social profile"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        normalized_id = self.bot.normalize_profile_id(platform, profile_url)
        if not normalized_id:
            await interaction.response.send_message(
                "❌ Invalid profile URL.",
                ephemeral=True
            )
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Check global ban
                cursor = conn.execute(
                    "SELECT * FROM banned_profiles WHERE normalized_id = ?",
                    (normalized_id,)
                )
                if cursor.fetchone():
                    await interaction.response.send_message(
                        "❌ This profile is banned.",
                        ephemeral=True
                    )
                    return
                
                # Check global uniqueness
                cursor = conn.execute(
                    "SELECT * FROM social_profiles WHERE normalized_id = ?",
                    (normalized_id,)
                )
                if cursor.fetchone():
                    await interaction.response.send_message(
                        "❌ This profile is already registered to another user.",
                        ephemeral=True
                    )
                    return
                
                # Ensure user exists
                conn.execute(
                    "INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)",
                    (str(user.id), str(user))
                )
                
                # Add profile
                conn.execute('''
                    INSERT INTO social_profiles 
                    (discord_id, platform, profile_url, normalized_id, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (str(user.id), platform, profile_url, normalized_id))
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Profile registered for <@{user.id}>. Status: Pending",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PROFILE_REGISTERED',
                    str(interaction.user.id),
                    str(user.id),
                    {'platform': platform, 'profile_url': profile_url}
                )
                
        except Exception as e:
            logger.error(f"Error in register: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while registering profile.",
                ephemeral=True
            )
    
    @app_commands.command(name="approval-page", description="[Staff] View pending approvals")
    async def approval_page(self, interaction: discord.Interaction):
        """Show approval queue"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Get pending profiles
                cursor = conn.execute('''
                    SELECT sp.*, u.username as discord_username
                    FROM social_profiles sp
                    JOIN users u ON sp.discord_id = u.discord_id
                    WHERE sp.status = 'pending'
                    ORDER BY sp.created_at DESC
                    LIMIT 10
                ''')
                pending_profiles = cursor.fetchall()
                
                # Get pending submissions
                cursor = conn.execute('''
                    SELECT s.*, u.username as discord_username, 
                           c.name as campaign_name, sp.profile_url
                    FROM submissions s
                    JOIN users u ON s.discord_id = u.discord_id
                    JOIN campaigns c ON s.campaign_id = c.id
                    JOIN social_profiles sp ON s.social_profile_id = sp.id
                    WHERE s.status = 'pending'
                    ORDER BY s.submitted_at DESC
                    LIMIT 10
                ''')
                pending_submissions = cursor.fetchall()
                
                embed = discord.Embed(
                    title="📋 Approval Queue",
                    description="Pending items requiring review",
                    color=discord.Color.yellow(),
                    timestamp=datetime.now()
                )
                
                if pending_profiles:
                    profile_text = "\n\n".join([
                        f"**{i+1}. {p[2].upper()}**\nUser: <@{p[1]}>\nProfile: {p[3]}\nSubmitted: <t:{int(datetime.fromisoformat(p[11]).timestamp())}:R>"
                        for i, p in enumerate(pending_profiles)
                    ])
                    embed.add_field(
                        name=f"📱 Pending Profiles ({len(pending_profiles)})",
                        value=profile_text,
                        inline=False
                    )
                
                if pending_submissions:
                    submission_text = "\n\n".join([
                        f"**{i+1}. {s[15]}**\nUser: <@{s[1]}>\nVideo: {s[4]}\nViews: {s[7]:,}\nSubmitted: <t:{int(datetime.fromisoformat(s[13]).timestamp())}:R>"
                        for i, s in enumerate(pending_submissions)
                    ])
                    embed.add_field(
                        name=f"📤 Pending Submissions ({len(pending_submissions)})",
                        value=submission_text,
                        inline=False
                    )
                
                if not pending_profiles and not pending_submissions:
                    embed.description = "✅ No pending items!"
                
                view = None
                if pending_profiles:
                    select_menu = discord.ui.Select(
                        custom_id="approval_select",
                        placeholder="Select item to review",
                        options=[
                            discord.SelectOption(
                                label=f"{p[2]} - {p[12][:20]}",
                                description=f"Profile {i+1}",
                                value=f"review_profile:{p[0]}"
                            )
                            for i, p in enumerate(pending_profiles)
                        ]
                    )
                    
                    async def select_callback(interaction: discord.Interaction):
                        await self.handle_approval_select(interaction, select_menu.values[0])
                    
                    select_menu.callback = select_callback
                    
                    view = discord.ui.View(timeout=None)
                    view.add_item(select_menu)
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in approval_page: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching approval queue.",
                ephemeral=True
            )
     async def handle_approval_select(self, interaction: discord.Interaction, value: str):
        """Handle approval selection"""
        if not await self.bot.check_permission(interaction, 'staff'):
            await interaction.response.send_message(
                "❌ You don't have permission to do that.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            action, profile_id = value.split(":")
            
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM social_profiles WHERE id = ?",
                    (profile_id,)
                )
                profile = cursor.fetchone()
                
                if not profile:
                    await interaction.followup.send(
                        "❌ Profile not found.",
                        ephemeral=True
                    )
                    return
                
                # Create approval view
                view = discord.ui.View(timeout=None)
                view.add_item(discord.ui.Button(
                    custom_id=f"approve_profile:{profile_id}",
                    label="✅ Approve",
                    style=discord.ButtonStyle.success
                ))
                view.add_item(discord.ui.Button(
                    custom_id=f"reject_profile:{profile_id}",
                    label="❌ Reject",
                    style=discord.ButtonStyle.danger
                ))
                view.add_item(discord.ui.Button(
                    custom_id=f"ban_profile_direct:{profile_id}",
                    label="🚫 Ban",
                    style=discord.ButtonStyle.secondary
                ))
                
                embed = discord.Embed(
                    title="👤 Profile Review",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="User", value=f"<@{profile[1]}>", inline=True)
                embed.add_field(name="Platform", value=profile[2], inline=True)
                embed.add_field(name="Profile URL", value=profile[3], inline=False)
                embed.add_field(name="Status", value=profile[5], inline=True)
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in handle_approval_select: {e}")
            await interaction.followup.send(
                "❌ An error occurred.",
                ephemeral=True
            )
    
    @app_commands.command(name="ban-social", description="[Staff] Ban a social profile")
    @app_commands.describe(
        platform="Platform",
        profile_url="Profile link",
        reason="Ban reason"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Instagram", value="instagram"),
        app_commands.Choice(name="TikTok", value="tiktok"),
        app_commands.Choice(name="YouTube", value="youtube")
    ])
    async def ban_social(self, interaction: discord.Interaction, 
                        platform: str, profile_url: str, reason: str):
        """Ban a social profile"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        normalized_id = self.bot.normalize_profile_id(platform, profile_url)
        if not normalized_id:
            await interaction.response.send_message(
                "❌ Invalid profile URL.",
                ephemeral=True
            )
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Check if already banned
                cursor = conn.execute(
                    "SELECT * FROM banned_profiles WHERE normalized_id = ?",
                    (normalized_id,)
                )
                if cursor.fetchone():
                    await interaction.response.send_message(
                        "❌ Profile is already banned.",
                        ephemeral=True
                    )
                    return
                
                # Add to banned list
                conn.execute('''
                    INSERT INTO banned_profiles 
                    (platform, profile_url, normalized_id, reason, banned_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (platform, profile_url, normalized_id, reason, str(interaction.user.id)))
                
                # Update profile status if exists
                conn.execute(
                    "UPDATE social_profiles SET status = 'banned' WHERE normalized_id = ?",
                    (normalized_id,)
                )
                
                # Stop tracking for this profile
                conn.execute('''
                    UPDATE submissions s
                    SET tracking = FALSE
                    WHERE social_profile_id IN (
                        SELECT id FROM social_profiles WHERE normalized_id = ?
                    )
                ''', (normalized_id,))
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Profile banned: {profile_url}",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PROFILE_BANNED',
                    str(interaction.user.id),
                    details={
                        'platform': platform,
                        'profile_url': profile_url,
                        'reason': reason
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in ban_social: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
    
    @app_commands.command(name="ban-list", description="[Staff] List banned profiles")
    async def ban_list(self, interaction: discord.Interaction):
        """List banned profiles"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM banned_profiles 
                    ORDER BY banned_at DESC
                    LIMIT 20
                ''')
                banned_profiles = cursor.fetchall()
                
                if not banned_profiles:
                    await interaction.followup.send(
                        "No banned profiles.",
                        ephemeral=True
                    )
                    return
                
                embed = discord.Embed(
                    title="🚫 Banned Profiles",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                for i, ban in enumerate(banned_profiles):
                    banned_at = datetime.fromisoformat(ban[7])
                    embed.add_field(
                        name=f"{i+1}. {ban[1].upper()}",
                        value=f"**Profile:** {ban[2]}\n**Reason:** {ban[4]}\n**Banned by:** <@{ban[5]}>\n**Date:** <t:{int(banned_at.timestamp())}:R>",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in ban_list: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching banned profiles.",
                ephemeral=True
            )
    
    @app_commands.command(name="ban-remove", description="[Admin] Remove ban from profile")
    @app_commands.describe(profile_id="Banned profile ID")
    async def ban_remove(self, interaction: discord.Interaction, profile_id: str):
        """Remove ban from profile"""
        if not await self.bot.enforce_permission(interaction, 'admin'):
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM banned_profiles WHERE id = ?",
                    (profile_id,)
                )
                ban = cursor.fetchone()
                
                if not ban:
                    await interaction.response.send_message(
                        "❌ Ban record not found.",
                        ephemeral=True
                    )
                    return
                
                # Remove from banned list
                conn.execute(
                    "DELETE FROM banned_profiles WHERE id = ?",
                    (profile_id,)
                )
                
                # Update profile status (doesn't auto-approve)
                conn.execute(
                    "UPDATE social_profiles SET status = 'rejected' WHERE normalized_id = ?",
                    (ban[3],)
                )
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Ban removed for profile: {ban[2]}\nNote: Profile not auto-approved.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'BAN_REMOVED',
                    str(interaction.user.id),
                    details={'profile_url': ban[2], 'platform': ban[1]}
                )
                
        except Exception as e:
            logger.error(f"Error in ban_remove: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while removing ban.",
                ephemeral=True
          )
              # Campaign Commands
    
    @app_commands.command(name="campaign-create", description="[Admin] Create new campaign")
    @app_commands.describe(
        name="Campaign name",
        platform="Platform",
        total_budget="Total budget in USD",
        rate_100k="Rate per 100K views",
        rate_1m="Rate per 1M views",
        min_views="Minimum views required",
        min_followers="Minimum followers required",
        max_earn_creator="Max earnings per creator",
        max_earn_post="Max earnings per post"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Instagram", value="instagram"),
        app_commands.Choice(name="TikTok", value="tiktok"),
        app_commands.Choice(name="YouTube", value="youtube")
    ])
    async def campaign_create(self, interaction: discord.Interaction,
                            name: str, platform: str, total_budget: float,
                            rate_100k: float, rate_1m: float, min_views: int,
                            min_followers: int, max_earn_creator: float,
                            max_earn_post: float):
        """Create a new campaign"""
        if not await self.bot.enforce_permission(interaction, 'admin'):
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Check if campaign exists
                cursor = conn.execute(
                    "SELECT * FROM campaigns WHERE name = ?",
                    (name,)
                )
                if cursor.fetchone():
                    await interaction.response.send_message(
                        "❌ Campaign with this name already exists.",
                        ephemeral=True
                    )
                    return
                
                # Create campaign
                conn.execute('''
                    INSERT INTO campaigns 
                    (name, platform, total_budget, rate_per_100k, rate_per_1m, 
                     min_views, min_followers, max_earn_per_creator, max_earn_per_post,
                     created_by, remaining_budget)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name, platform, total_budget, rate_100k, rate_1m,
                    min_views, min_followers, max_earn_creator, max_earn_post,
                    str(interaction.user.id), total_budget
                ))
                
                conn.commit()
                
                await interaction.response.send_message(
                    f'✅ Campaign "{name}" created successfully!',
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'CAMPAIGN_CREATED',
                    str(interaction.user.id),
                    details={
                        'campaign_name': name,
                        'platform': platform,
                        'budget': total_budget
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in campaign_create: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while creating campaign.",
                ephemeral=True
            )
    
    @app_commands.command(name="campaign-list", description="List all campaigns")
    async def campaign_list(self, interaction: discord.Interaction):
        """List all campaigns"""
        await interaction.response.defer()
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM campaigns 
                    ORDER BY 
                        CASE status 
                            WHEN 'live' THEN 1 
                            ELSE 2 
                        END,
                        created_at DESC
                ''')
                campaigns = cursor.fetchall()
                
                if not campaigns:
                    await interaction.followup.send("No campaigns found.")
                    return
                
                embed = discord.Embed(
                    title="📊 Campaign List",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                for campaign in campaigns:
                    status_emoji = "🟢" if campaign[10] == 'live' else "🔴"
                    value = f"""
                        **Platform:** {campaign[2]}
                        **Budget:** ${campaign[12]:.2f} / ${campaign[3]:.2f}
                        **Rate:** ${campaign[4]}/100K | ${campaign[5]}/1M
                        **Min Views:** {campaign[6]:,}
                        **Status:** {status_emoji} {campaign[10]}
                    """
                    embed.add_field(
                        name=f"{campaign[1]}",
                        value=value,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error in campaign_list: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching campaigns."
            )
    
    @app_commands.command(name="campaign-end", description="[Admin] End a campaign")
    @app_commands.describe(campaign="Campaign name")
    @app_commands.autocomplete(campaign=async def campaign_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for campaign names"""
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.execute('''
                    SELECT name FROM campaigns 
                    WHERE status = 'live' AND name LIKE ?
                    LIMIT 10
                ''', (f'%{current}%',))
                campaigns = cursor.fetchall()
                return [
                    app_commands.Choice(name=campaign[0], value=campaign[0])
                    for campaign in campaigns
                ]
        except:
            return []
    )
    async def campaign_end(self, interaction: discord.Interaction, campaign: str):
        """End a campaign"""
        if not await self.bot.enforce_permission(interaction, 'admin'):
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM campaigns WHERE name = ? AND status = 'live'",
                    (campaign,)
                )
                campaign_data = cursor.fetchone()
                
                if not campaign_data:
                    await interaction.response.send_message(
                        "❌ Campaign not found or already ended.",
                        ephemeral=True
                    )
                    return
                
                # Update campaign status
                conn.execute(
                    "UPDATE campaigns SET status = 'ended', ended_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), campaign_data[0])
                )
                
                # Stop tracking all submissions
                conn.execute(
                    "UPDATE submissions SET tracking = FALSE WHERE campaign_id = ?",
                    (campaign_data[0],)
                )
                
                conn.commit()
                
                await interaction.response.send_message(
                    f'✅ Campaign "{campaign}" ended successfully.',
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'CAMPAIGN_ENDED',
                    str(interaction.user.id),
                    details={
                        'campaign_name': campaign,
                        'remaining_budget': campaign_data[12]
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in campaign_end: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while ending campaign.",
                ephemeral=True
            )
        # Payment Commands
    
    @app_commands.command(name="wallet", description="[Staff] View user wallet info")
    @app_commands.describe(user="User to check")
    async def wallet(self, interaction: discord.Interaction, user: discord.User):
        """View user wallet information"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT u.*,
                           SUM(s.earnings) as total_earned,
                           COUNT(DISTINCT s.id) as total_submissions
                    FROM users u
                    LEFT JOIN submissions s ON u.discord_id = s.discord_id
                    WHERE u.discord_id = ?
                ''', (str(user.id),))
                
                user_data = cursor.fetchone()
                
                if not user_data:
                    await interaction.followup.send(
                        "❌ User not found.",
                        ephemeral=True
                    )
                    return
                
                # Get pending payouts
                cursor = conn.execute('''
                    SELECT p.*, c.name as campaign_name
                    FROM payouts p
                    JOIN campaigns c ON p.campaign_id = c.id
                    WHERE p.discord_id = ? AND p.status = 'pending'
                ''', (str(user.id),))
                
                pending_payouts = cursor.fetchall()
                
                embed = discord.Embed(
                    title="💰 Wallet Information",
                    description=f"User: <@{user.id}>",
                    color=discord.Color.purple(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="Total Earnings",
                    value=f"${user_data[3]:.2f}",
                    inline=True
                )
                embed.add_field(
                    name="Paid",
                    value=f"${user_data[4]:.2f}",
                    inline=True
                )
                embed.add_field(
                    name="Pending",
                    value=f"${user_data[5]:.2f}",
                    inline=True
                )
                embed.add_field(
                    name="USDT Wallet",
                    value=f"`{user_data[2]}`" if user_data[2] else "Not set",
                    inline=False
                )
                
                if pending_payouts:
                    payout_text = "\n".join([
                        f"**{p[7]}:** ${p[3]:.2f}"
                        for p in pending_payouts
                    ])
                    embed.add_field(name="Pending Payouts", value=payout_text)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in wallet: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching wallet info.",
                ephemeral=True
            )
    
    @app_commands.command(name="payout-mark-paid", description="[Staff] Mark payout as paid")
    @app_commands.describe(
        user="User",
        campaign="Campaign name",
        amount="Amount in USD",
        tx_hash="USDT transaction hash"
    )
    async def payout_mark_paid(self, interaction: discord.Interaction,
                              user: discord.User, campaign: str,
                              amount: float, tx_hash: str):
        """Mark a payout as paid"""
        if not await self.bot.enforce_permission(interaction, 'staff'):
            return
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                # Get campaign
                cursor = conn.execute(
                    "SELECT * FROM campaigns WHERE name = ?",
                    (campaign,)
                )
                campaign_data = cursor.fetchone()
                
                if not campaign_data:
                    await interaction.response.send_message(
                        "❌ Campaign not found.",
                        ephemeral=True
                    )
                    return
                
                # Create payout record
                conn.execute('''
                    INSERT INTO payouts 
                    (discord_id, campaign_id, amount, status, usdt_tx_hash, paid_by, paid_at)
                    VALUES (?, ?, ?, 'paid', ?, ?, ?)
                ''', (
                    str(user.id),
                    campaign_data[0],
                    amount,
                    tx_hash,
                    str(interaction.user.id),
                    datetime.now().isoformat()
                ))
                
                # Update user earnings
                conn.execute('''
                    UPDATE users 
                    SET paid_earnings = paid_earnings + ?,
                        pending_earnings = pending_earnings - ?
                    WHERE discord_id = ?
                ''', (amount, amount, str(user.id)))
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Payout marked as paid for <@{user.id}>. TX: `{tx_hash}`",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PAYOUT_MARKED_PAID',
                    str(interaction.user.id),
                    str(user.id),
                    {
                        'campaign': campaign,
                        'amount': amount,
                        'tx_hash': tx_hash
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in payout_mark_paid: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while marking payout as paid.",
                ephemeral=True
            )

class Events(commands.Cog):
    def __init__(self, bot: CLBot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Logged in as {self.bot.user}")
        
        # Get channels
        if LOG_CHANNEL_ID:
            self.bot.log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if self.bot.log_channel:
                logger.info(f"Log channel set: {self.bot.log_channel.name}")
        
        if SUBMISSION_CHANNEL_ID:
            self.bot.submission_channel = self.bot.get_channel(SUBMISSION_CHANNEL_ID)
            if self.bot.submission_channel:
                logger.info(f"Submission channel set: {self.bot.submission_channel.name}")
        
        await self.bot.log_action('BOT_STARTED', 'system')
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions"""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get('custom_id', '')
        
        if not await self.bot.check_permission(interaction, 'staff'):
            await interaction.response.send_message(
                "❌ You don't have permission to do that.",
                ephemeral=True
            )
            return
        
        if custom_id.startswith('approve_submission:'):
            await self.approve_submission(interaction, custom_id)
        elif custom_id.startswith('reject_submission:'):
            await self.reject_submission_modal(interaction, custom_id)
        elif custom_id.startswith('ban_profile:'):
            await self.ban_profile_modal(interaction, custom_id)
        elif custom_id.startswith('approve_profile:'):
            await self.approve_profile(interaction, custom_id)
        elif custom_id.startswith('reject_profile:'):
            await self.reject_profile_modal(interaction, custom_id)
        elif custom_id.startswith('ban_profile_direct:'):
            await self.ban_profile_modal(interaction, custom_id.replace('_direct', ''))
    
    async def approve_submission(self, interaction: discord.Interaction, custom_id: str):
        """Approve a submission"""
        submission_id = int(custom_id.split(':')[1])
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT s.*, u.username, c.name as campaign_name
                    FROM submissions s
                    JOIN users u ON s.discord_id = u.discord_id
                    JOIN campaigns c ON s.campaign_id = c.id
                    WHERE s.id = ?
                ''', (submission_id,))
                
                submission = cursor.fetchone()
                
                if not submission:
                    await interaction.response.send_message(
                        "❌ Submission not found.",
                        ephemeral=True
                    )
                    return
                
                # Update submission
                conn.execute('''
                    UPDATE submissions 
                    SET status = 'approved', 
                        tracking = TRUE,
                        approved_at = ?,
                        approved_by = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), str(interaction.user.id), submission_id))
                
                # Update message in submission channel
                if submission[14] and self.bot.submission_channel:  # message_id
                    try:
                        message = await self.bot.submission_channel.fetch_message(int(submission[14]))
                        
                        embed = message.embeds[0]
                        embed.title = "✅ Approved Submission"
                        embed.color = discord.Color.green()
                        embed.add_field(
                            name="Approved By",
                            value=f"<@{interaction.user.id}>",
                            inline=True
                        )
                        embed.add_field(
                            name="Approved At",
                            value=f"<t:{int(datetime.now().timestamp())}:R>",
                            inline=True
                        )
                        
                        await message.edit(embed=embed, view=None)
                        
                    except Exception as e:
                        logger.error(f"Failed to update submission message: {e}")
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Submission #{submission_id} approved. Tracking started.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'SUBMISSION_APPROVED',
                    str(interaction.user.id),
                    str(submission[1]),
                    {
                        'submission_id': submission_id,
                        'campaign': submission[15]
                    }
                )
                
        except Exception as e:
            logger.error(f"Error approving submission: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while approving submission.",
                ephemeral=True
)
   async def reject_submission_modal(self, interaction: discord.Interaction, custom_id: str):
        """Show modal for rejection reason"""
        submission_id = int(custom_id.split(':')[1])
        
        modal = discord.ui.Modal(title="Reject Submission")
        modal.custom_id = f"reject_submission_modal:{submission_id}"
        
        reason_input = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="rejection_reason"
        )
        modal.add_item(reason_input)
        
        await interaction.response.send_modal(modal)
    
    async def ban_profile_modal(self, interaction: discord.Interaction, custom_id: str):
        """Show modal for ban reason"""
        profile_id = int(custom_id.split(':')[1])
        
        modal = discord.ui.Modal(title="Ban Profile")
        modal.custom_id = f"ban_profile_modal:{profile_id}"
        
        reason_input = discord.ui.TextInput(
            label="Ban reason",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="ban_reason"
        )
        modal.add_item(reason_input)
        
        await interaction.response.send_modal(modal)
    
    async def reject_profile_modal(self, interaction: discord.Interaction, custom_id: str):
        """Show modal for profile rejection"""
        profile_id = int(custom_id.split(':')[1])
        
        modal = discord.ui.Modal(title="Reject Profile")
        modal.custom_id = f"reject_profile_modal:{profile_id}"
        
        reason_input = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="rejection_reason"
        )
        modal.add_item(reason_input)
        
        await interaction.response.send_modal(modal)
    
    async def approve_profile(self, interaction: discord.Interaction, custom_id: str):
        """Approve a profile"""
        profile_id = int(custom_id.split(':')[1])
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                conn.execute(
                    "UPDATE social_profiles SET status = 'approved', verified_at = ?, verified_by = ? WHERE id = ?",
                    (datetime.now().isoformat(), str(interaction.user.id), profile_id)
                )
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Profile #{profile_id} approved.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PROFILE_APPROVED',
                    str(interaction.user.id),
                    details={'profile_id': profile_id}
                )
                
        except Exception as e:
            logger.error(f"Error approving profile: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while approving profile.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_modal_submit(self, interaction: discord.Interaction):
        """Handle modal submissions"""
        custom_id = interaction.data.get('custom_id', '')
        
        if not await self.bot.check_permission(interaction, 'staff'):
            await interaction.response.send_message(
                "❌ You don't have permission to do that.",
                ephemeral=True
            )
            return
        
        if custom_id.startswith('reject_submission_modal:'):
            await self.process_rejection(interaction, custom_id)
        elif custom_id.startswith('ban_profile_modal:'):
            await self.process_ban(interaction, custom_id)
        elif custom_id.startswith('reject_profile_modal:'):
            await self.process_profile_rejection(interaction, custom_id)
    
    async def process_rejection(self, interaction: discord.Interaction, custom_id: str):
        """Process submission rejection"""
        submission_id = int(custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute('''
                    SELECT s.*, u.username, c.name as campaign_name
                    FROM submissions s
                    JOIN users u ON s.discord_id = u.discord_id
                    JOIN campaigns c ON s.campaign_id = c.id
                    WHERE s.id = ?
                ''', (submission_id,))
                
                submission = cursor.fetchone()
                
                if not submission:
                    await interaction.response.send_message(
                        "❌ Submission not found.",
                        ephemeral=True
                    )
                    return
                
                # Update submission
                conn.execute(
                    "UPDATE submissions SET status = 'rejected' WHERE id = ?",
                    (submission_id,)
                )
                
                # Update message in submission channel
                if submission[14] and self.bot.submission_channel:
                    try:
                        message = await self.bot.submission_channel.fetch_message(int(submission[14]))
                        
                        embed = message.embeds[0]
                        embed.title = "❌ Rejected Submission"
                        embed.color = discord.Color.red()
                        embed.add_field(
                            name="Rejected By",
                            value=f"<@{interaction.user.id}>",
                            inline=True
                        )
                        embed.add_field(
                            name="Reason",
                            value=reason,
                            inline=False
                        )
                        
                        await message.edit(embed=embed, view=None)
                        
                    except Exception as e:
                        logger.error(f"Failed to update submission message: {e}")
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Submission #{submission_id} rejected.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'SUBMISSION_REJECTED',
                    str(interaction.user.id),
                    str(submission[1]),
                    {
                        'submission_id': submission_id,
                        'reason': reason
                    }
                )
                
        except Exception as e:
            logger.error(f"Error processing rejection: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while rejecting submission.",
                ephemeral=True
            )
    
    async def process_ban(self, interaction: discord.Interaction, custom_id: str):
        """Process profile ban"""
        profile_id = int(custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM social_profiles WHERE id = ?",
                    (profile_id,)
                )
                profile = cursor.fetchone()
                
                if not profile:
                    await interaction.response.send_message(
                        "❌ Profile not found.",
                        ephemeral=True
                    )
                    return
                
                # Add to banned list
                conn.execute('''
                    INSERT INTO banned_profiles 
                    (platform, profile_url, normalized_id, reason, banned_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    profile[2],  # platform
                    profile[3],  # profile_url
                    profile[4],  # normalized_id
                    reason,
                    str(interaction.user.id)
                ))
                
                # Update profile status
                conn.execute(
                    "UPDATE social_profiles SET status = 'banned' WHERE id = ?",
                    (profile_id,)
                )
                
                # Stop tracking for this profile
                conn.execute(
                    "UPDATE submissions SET tracking = FALSE WHERE social_profile_id = ?",
                    (profile_id,)
                )
                
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Profile banned: {profile[3]}",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PROFILE_BANNED_MODAL',
                    str(interaction.user.id),
                    details={
                        'profile_id': profile_id,
                        'profile_url': profile[3],
                        'reason': reason
                    }
                )
                
        except Exception as e:
            logger.error(f"Error processing ban: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
    
    async def process_profile_rejection(self, interaction: discord.Interaction, custom_id: str):
        """Process profile rejection"""
        profile_id = int(custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                conn.execute(
                    "UPDATE social_profiles SET status = 'rejected', rejection_reason = ? WHERE id = ?",
                    (reason, profile_id)
                )
                conn.commit()
                
                await interaction.response.send_message(
                    f"✅ Profile #{profile_id} rejected.",
                    ephemeral=True
                )
                
                await self.bot.log_action(
                    'PROFILE_REJECTED',
                    str(interaction.user.id),
                    details={'profile_id': profile_id, 'reason': reason}
                )
                
        except Exception as e:
            logger.error(f"Error processing profile rejection: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while rejecting profile.",
                ephemeral=True
            )

async def main():
    """Main function to run the bot"""
    bot = CLBot()
    
    # Graceful shutdown
    async def shutdown():
        logger.info("Shutting down...")
        bot.track_views.stop()
        bot.cleanup_data.stop()
        await bot.close()
    
    import signal
    signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(shutdown()))
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(shutdown()))
    
    # Run the bot
    try:
        await bot.start(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())       
