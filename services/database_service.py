import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from database import Database
from models import User, SocialProfile, Campaign, Submission, BannedProfile, Payout

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

class DatabaseService:
    def __init__(self):
        self.db_path = os.getenv('DATABASE_PATH', 'database.sqlite')
        self.database = Database(self.db_path)
        
    def get_current_ist_time(self):
        """Get current time in IST"""
        return datetime.now(IST)
        
    async def initialize(self):
        """Initialize database service"""
        self.database.initialize()
        
    async def close(self):
        """Close database connection"""
        self.database.close()
        
    # User operations
    async def create_user_if_not_exists(self, discord_id: str, username: str) -> bool:
        """Create user if not exists"""
        existing = self.database.fetch_one(
            "SELECT * FROM users WHERE discord_id = ?",
            (discord_id,)
        )
        
        if not existing:
            self.database.execute(
                "INSERT INTO users (discord_id, username) VALUES (?, ?)",
                (discord_id, username)
            )
            return True
        return False
        
    async def get_user(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID"""
        row = self.database.fetch_one(
            "SELECT * FROM users WHERE discord_id = ?",
            (discord_id,)
        )
        if row:
            return User(
                discord_id=row['discord_id'],
                username=row['username'],
                usdt_wallet=row['usdt_wallet'],
                total_earnings=row['total_earnings'] or 0.0,
                paid_earnings=row['paid_earnings'] or 0.0,
                pending_earnings=row['pending_earnings'] or 0.0,
                created_at=row['created_at']
            )
        return None
        
    async def update_user_wallet(self, discord_id: str, wallet: str):
        """Update user's USDT wallet"""
        self.database.execute(
            "UPDATE users SET usdt_wallet = ? WHERE discord_id = ?",
            (wallet, discord_id)
        )
        
    async def get_user_stats(self, discord_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        row = self.database.fetch_one('''
            SELECT 
                COUNT(DISTINCT s.id) as total_submissions,
                COUNT(DISTINCT CASE WHEN s.status = 'approved' THEN s.id END) as approved_submissions,
                COUNT(DISTINCT s.campaign_id) as campaigns_participated,
                SUM(s.current_views) as total_views,
                SUM(s.earnings) as total_earned,
                MAX(s.submitted_at) as last_submission
            FROM submissions s
            WHERE s.discord_id = ?
        ''', (discord_id,))
        
        if row:
            return {
                'total_submissions': row['total_submissions'] or 0,
                'approved_submissions': row['approved_submissions'] or 0,
                'campaigns_participated': row['campaigns_participated'] or 0,
                'total_views': row['total_views'] or 0,
                'total_earned': row['total_earned'] or 0.0,
                'last_submission': row['last_submission']
            }
        return {}
        
    async def get_user_profiles(self, discord_id: str) -> List[SocialProfile]:
        """Get user's social profiles"""
        rows = self.database.fetch_all(
            "SELECT * FROM social_profiles WHERE discord_id = ? ORDER BY created_at DESC",
            (discord_id,)
        )
        profiles = []
        for row in rows:
            profiles.append(SocialProfile(
                id=row['id'],
                discord_id=row['discord_id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                status=row['status'],
                followers=row['followers'] or 0,
                tier=row['tier'],
                verified_at=row['verified_at'],
                verified_by=row['verified_by'],
                rejection_reason=row['rejection_reason'],
                created_at=row['created_at']
            ))
        return profiles
        
    async def get_user_active_campaigns(self, discord_id: str) -> List[Dict]:
        """Get user's active campaigns"""
        rows = self.database.fetch_all('''
            SELECT DISTINCT c.name, s.status
            FROM submissions s
            JOIN campaigns c ON s.campaign_id = c.id
            WHERE s.discord_id = ? AND c.status = 'live' AND s.status = 'approved'
        ''', (discord_id,))
        return [dict(row) for row in rows]
        
    # Profile operations
    async def create_social_profile(self, discord_id: str, platform: str, 
                                   profile_url: str, normalized_id: str) -> int:
        """Create social profile"""
        self.database.execute('''
            INSERT INTO social_profiles 
            (discord_id, platform, profile_url, normalized_id, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (discord_id, platform, profile_url, normalized_id))
        return self.database.get_lastrowid()
        
    async def get_profile_by_id(self, profile_id: int) -> Optional[SocialProfile]:
        """Get profile by ID"""
        row = self.database.fetch_one(
            "SELECT * FROM social_profiles WHERE id = ?",
            (profile_id,)
        )
        if row:
            return SocialProfile(
                id=row['id'],
                discord_id=row['discord_id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                status=row['status'],
                followers=row['followers'] or 0,
                tier=row['tier'],
                verified_at=row['verified_at'],
                verified_by=row['verified_by'],
                rejection_reason=row['rejection_reason'],
                created_at=row['created_at']
            )
        return None
        
    async def get_profile_by_url(self, discord_id: str, profile_url: str) -> Optional[SocialProfile]:
        """Get profile by URL"""
        row = self.database.fetch_one('''
            SELECT * FROM social_profiles 
            WHERE discord_id = ? AND profile_url = ?
        ''', (discord_id, profile_url))
        if row:
            return SocialProfile(
                id=row['id'],
                discord_id=row['discord_id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                status=row['status'],
                followers=row['followers'] or 0,
                tier=row['tier'],
                verified_at=row['verified_at'],
                verified_by=row['verified_by'],
                rejection_reason=row['rejection_reason'],
                created_at=row['created_at']
            )
        return None
        
    async def get_profile_by_normalized_id(self, normalized_id: str) -> Optional[SocialProfile]:
        """Get profile by normalized ID"""
        row = self.database.fetch_one(
            "SELECT * FROM social_profiles WHERE normalized_id = ?",
            (normalized_id,)
        )
        if row:
            return SocialProfile(
                id=row['id'],
                discord_id=row['discord_id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                status=row['status'],
                followers=row['followers'] or 0,
                tier=row['tier'],
                verified_at=row['verified_at'],
                verified_by=row['verified_by'],
                rejection_reason=row['rejection_reason'],
                created_at=row['created_at']
            )
        return None
        
    async def get_pending_profiles(self, limit: int = 10) -> List[SocialProfile]:
        """Get pending profiles"""
        rows = self.database.fetch_all('''
            SELECT sp.*, u.username as discord_username
            FROM social_profiles sp
            JOIN users u ON sp.discord_id = u.discord_id
            WHERE sp.status = 'pending'
            ORDER BY sp.created_at DESC
            LIMIT ?
        ''', (limit,))
        profiles = []
        for row in rows:
            profiles.append(SocialProfile(
                id=row['id'],
                discord_id=row['discord_id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                status=row['status'],
                followers=row['followers'] or 0,
                tier=row['tier'],
                verified_at=row['verified_at'],
                verified_by=row['verified_by'],
                rejection_reason=row['rejection_reason'],
                created_at=row['created_at']
            ))
        return profiles
        
    async def approve_profile(self, profile_id: int, approved_by: str):
        """Approve profile"""
        current_time = self.get_current_ist_time()
        self.database.execute('''
            UPDATE social_profiles 
            SET status = 'approved', verified_at = ?, verified_by = ?
            WHERE id = ?
        ''', (current_time.isoformat(), approved_by, profile_id))
        
    async def reject_profile(self, profile_id: int, reason: str):
        """Reject profile"""
        self.database.execute(
            "UPDATE social_profiles SET status = 'rejected', rejection_reason = ? WHERE id = ?",
            (reason, profile_id)
        )
        
    # Ban operations
    async def get_banned_profile(self, normalized_id: str) -> Optional[BannedProfile]:
        """Get banned profile"""
        row = self.database.fetch_one(
            "SELECT * FROM banned_profiles WHERE normalized_id = ?",
            (normalized_id,)
        )
        if row:
            return BannedProfile(
                id=row['id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                reason=row['reason'],
                banned_by=row['banned_by'],
                banned_at=row['banned_at']
            )
        return None
        
    async def get_ban_by_id(self, ban_id: int) -> Optional[BannedProfile]:
        """Get ban by ID"""
        row = self.database.fetch_one(
            "SELECT * FROM banned_profiles WHERE id = ?",
            (ban_id,)
        )
        if row:
            return BannedProfile(
                id=row['id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                reason=row['reason'],
                banned_by=row['banned_by'],
                banned_at=row['banned_at']
            )
        return None
        
    async def get_banned_profiles(self, limit: int = 20) -> List[BannedProfile]:
        """Get banned profiles"""
        rows = self.database.fetch_all(
            "SELECT * FROM banned_profiles ORDER BY banned_at DESC LIMIT ?",
            (limit,)
        )
        bans = []
        for row in rows:
            bans.append(BannedProfile(
                id=row['id'],
                platform=row['platform'],
                profile_url=row['profile_url'],
                normalized_id=row['normalized_id'],
                reason=row['reason'],
                banned_by=row['banned_by'],
                banned_at=row['banned_at']
            ))
        return bans
        
    async def ban_profile(self, platform: str, profile_url: str, 
                         normalized_id: str, reason: str, banned_by: str):
        """Ban a profile"""
        current_time = self.get_current_ist_time()
        # Add to banned list
        self.database.execute('''
            INSERT INTO banned_profiles 
            (platform, profile_url, normalized_id, reason, banned_by, banned_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (platform, profile_url, normalized_id, reason, banned_by, current_time.isoformat()))
        
        # Update profile status
        self.database.execute(
            "UPDATE social_profiles SET status = 'banned' WHERE normalized_id = ?",
            (normalized_id,)
        )
        
        # Stop tracking for this profile
        self.database.execute('''
            UPDATE submissions 
            SET tracking = FALSE
            WHERE social_profile_id IN (
                SELECT id FROM social_profiles WHERE normalized_id = ?
            )
        ''', (normalized_id,))
        
    async def remove_ban(self, normalized_id: str):
        """Remove ban"""
        # Remove from banned list
        self.database.execute(
            "DELETE FROM banned_profiles WHERE normalized_id = ?",
            (normalized_id,)
        )
        
        # Update profile status (doesn't auto-approve)
        self.database.execute(
            "UPDATE social_profiles SET status = 'rejected' WHERE normalized_id = ?",
            (normalized_id,)
        )
        
    # Campaign operations
    async def get_campaign_by_name(self, name: str) -> Optional[Campaign]:
        """Get campaign by name"""
        row = self.database.fetch_one(
            "SELECT * FROM campaigns WHERE name = ?",
            (name,)
        )
        if row:
            return Campaign(
                id=row['id'],
                name=row['name'],
                platform=row['platform'],
                total_budget=row['total_budget'],
                rate_per_100k=row['rate_per_100k'],
                rate_per_1m=row['rate_per_1m'],
                min_views=row['min_views'],
                min_followers=row['min_followers'],
                max_earn_per_creator=row['max_earn_per_creator'],
                max_earn_per_post=row['max_earn_per_post'],
                status=row['status'],
                created_by=row['created_by'],
                ended_at=row['ended_at'],
                remaining_budget=row['remaining_budget'],
                created_at=row['created_at']
            )
        return None
        
    async def get_campaign_by_id(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID"""
        row = self.database.fetch_one(
            "SELECT * FROM campaigns WHERE id = ?",
            (campaign_id,)
        )
        if row:
            return Campaign(
                id=row['id'],
                name=row['name'],
                platform=row['platform'],
                total_budget=row['total_budget'],
                rate_per_100k=row['rate_per_100k'],
                rate_per_1m=row['rate_per_1m'],
                min_views=row['min_views'],
                min_followers=row['min_followers'],
                max_earn_per_creator=row['max_earn_per_creator'],
                max_earn_per_post=row['max_earn_per_post'],
                status=row['status'],
                created_by=row['created_by'],
                ended_at=row['ended_at'],
                remaining_budget=row['remaining_budget'],
                created_at=row['created_at']
            )
        return None
        
    # Submission operations
    async def create_submission(self, discord_id: str, campaign_id: int, 
                               social_profile_id: int, video_url: str,
                               normalized_video_id: str, platform: str,
                               starting_views: int) -> int:
        """Create submission"""
        current_time = self.get_current_ist_time()
        self.database.execute('''
            INSERT INTO submissions 
            (discord_id, campaign_id, social_profile_id, video_url, normalized_video_id, 
             platform, starting_views, current_views, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            discord_id, campaign_id, social_profile_id, video_url,
            normalized_video_id, platform, starting_views, starting_views, current_time.isoformat()
        ))
        return self.database.get_lastrowid()
        
    async def get_submission_by_id(self, submission_id: int) -> Optional[Submission]:
        """Get submission by ID"""
        row = self.database.fetch_one(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,)
        )
        if row:
            return Submission(
                id=row['id'],
                discord_id=row['discord_id'],
                campaign_id=row['campaign_id'],
                social_profile_id=row['social_profile_id'],
                video_url=row['video_url'],
                normalized_video_id=row['normalized_video_id'],
                platform=row['platform'],
                starting_views=row['starting_views'],
                current_views=row['current_views'],
                earnings=row['earnings'] or 0.0,
                status=row['status'],
                tracking=bool(row['tracking']),
                submitted_at=row['submitted_at'],
                approved_at=row['approved_at'],
                approved_by=row['approved_by'],
                message_id=row['message_id']
            )
        return None
        
    async def get_submission_by_video_id(self, normalized_video_id: str) -> Optional[Submission]:
        """Get submission by video ID"""
        row = self.database.fetch_one(
            "SELECT * FROM submissions WHERE normalized_video_id = ?",
            (normalized_video_id,)
        )
        if row:
            return Submission(
                id=row['id'],
                discord_id=row['discord_id'],
                campaign_id=row['campaign_id'],
                social_profile_id=row['social_profile_id'],
                video_url=row['video_url'],
                normalized_video_id=row['normalized_video_id'],
                platform=row['platform'],
                starting_views=row['starting_views'],
                current_views=row['current_views'],
                earnings=row['earnings'] or 0.0,
                status=row['status'],
                tracking=bool(row['tracking']),
                submitted_at=row['submitted_at'],
                approved_at=row['approved_at'],
                approved_by=row['approved_by'],
                message_id=row['message_id']
            )
        return None
        
    async def get_pending_submissions(self, limit: int = 10) -> List[Dict]:
        """Get pending submissions"""
        rows = self.database.fetch_all('''
            SELECT s.*, u.username as discord_username, 
                   c.name as campaign_name, sp.profile_url
            FROM submissions s
            JOIN users u ON s.discord_id = u.discord_id
            JOIN campaigns c ON s.campaign_id = c.id
            JOIN social_profiles sp ON s.social_profile_id = sp.id
            WHERE s.status = 'pending'
            ORDER BY s.submitted_at DESC
            LIMIT ?
        ''', (limit,))
        
        submissions = []
        for row in rows:
            submissions.append({
                'id': row['id'],
                'discord_id': row['discord_id'],
                'campaign_name': row['campaign_name'],
                'video_url': row['video_url'],
                'starting_views': row['starting_views'],
                'submitted_at': row['submitted_at'],
                'profile_url': row['profile_url']
            })
        return submissions
        
    async def approve_submission(self, submission_id: int, approved_by: str):
        """Approve submission"""
        current_time = self.get_current_ist_time()
        self.database.execute('''
            UPDATE submissions 
            SET status = 'approved', 
                tracking = TRUE,
                approved_at = ?,
                approved_by = ?
            WHERE id = ?
        ''', (current_time.isoformat(), approved_by, submission_id))
        
    async def reject_submission(self, submission_id: int):
        """Reject submission"""
        self.database.execute(
            "UPDATE submissions SET status = 'rejected' WHERE id = ?",
            (submission_id,)
        )
        
    async def update_submission_message_id(self, submission_id: int, message_id: str):
        """Update submission message ID"""
        self.database.execute(
            "UPDATE submissions SET message_id = ? WHERE id = ?",
            (message_id, submission_id)
        )
        
    # Payout operations
    async def get_pending_payouts(self, discord_id: str) -> List[Dict]:
        """Get pending payouts for user"""
        rows = self.database.fetch_all('''
            SELECT p.*, c.name as campaign_name
            FROM payouts p
            JOIN campaigns c ON p.campaign_id = c.id
            WHERE p.discord_id = ? AND p.status = 'pending'
        ''', (discord_id,))
        return [dict(row) for row in rows]
        
    async def create_payout(self, discord_id: str, campaign_id: int,
                           amount: float, usdt_tx_hash: str, paid_by: str):
        """Create payout record"""
        current_time = self.get_current_ist_time()
        self.database.execute('''
            INSERT INTO payouts 
            (discord_id, campaign_id, amount, status, usdt_tx_hash, paid_by, paid_at)
            VALUES (?, ?, ?, 'paid', ?, ?, ?)
        ''', (
            discord_id, campaign_id, amount, usdt_tx_hash,
            paid_by, current_time.isoformat()
        ))
        
        # Update user earnings
        self.database.execute('''
            UPDATE users 
            SET paid_earnings = paid_earnings + ?,
                pending_earnings = pending_earnings - ?
            WHERE discord_id = ?
        ''', (amount, amount, discord_id))
        
    # Log operations
    async def log_action(self, action_type: str, performed_by: str,
                        target_user: Optional[str] = None, details: Dict[str, Any] = None):
        """Log action to database"""
        import json
        current_time = self.get_current_ist_time()
        self.database.execute(
            "INSERT INTO activity_logs (action_type, performed_by, target_user, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (action_type, performed_by, target_user, json.dumps(details) if details else None, current_time.isoformat())
        )
        
    # Other methods
    async def update_submission_tracking(self, submission_id: int, tracking: bool):
        """Update submission tracking status"""
        self.database.execute(
            "UPDATE submissions SET tracking = ? WHERE id = ?",
            (tracking, submission_id)
        )
        
    async def cleanup_old_logs(self, days: int):
        """Clean up old logs"""
        self.database.execute(
            f"DELETE FROM activity_logs WHERE timestamp < datetime('now', '-{days} days')"
        )
        
    async def cleanup_old_view_history(self, days: int):
        """Clean up old view history"""
        self.database.execute(
            f"DELETE FROM view_history WHERE recorded_at < datetime('now', '-{days} days')"
        )
