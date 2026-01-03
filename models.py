from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class Platform(Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"

class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BANNED = "banned"
    LIVE = "live"
    ENDED = "ended"
    PAID = "paid"
    PROCESSING = "processing"

@dataclass
class User:
    discord_id: str
    username: str
    usdt_wallet: Optional[str] = None
    total_earnings: float = 0.0
    paid_earnings: float = 0.0
    pending_earnings: float = 0.0
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
            discord_id=row['discord_id'],
            username=row['username'],
            usdt_wallet=row['usdt_wallet'],
            total_earnings=row['total_earnings'],
            paid_earnings=row['paid_earnings'],
            pending_earnings=row['pending_earnings'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

@dataclass
class SocialProfile:
    id: Optional[int] = None
    discord_id: str = ""
    platform: str = ""
    profile_url: str = ""
    normalized_id: str = ""
    status: str = Status.PENDING.value
    followers: int = 0
    tier: Optional[str] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            discord_id=row['discord_id'],
            platform=row['platform'],
            profile_url=row['profile_url'],
            normalized_id=row['normalized_id'],
            status=row['status'],
            followers=row['followers'],
            tier=row['tier'],
            verified_at=datetime.fromisoformat(row['verified_at']) if row['verified_at'] else None,
            verified_by=row['verified_by'],
            rejection_reason=row['rejection_reason'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

@dataclass
class Campaign:
    id: Optional[int] = None
    name: str = ""
    platform: str = ""
    total_budget: float = 0.0
    rate_per_100k: float = 0.0
    rate_per_1m: float = 0.0
    min_views: int = 0
    min_followers: int = 0
    max_earn_per_creator: float = 0.0
    max_earn_per_post: float = 0.0
    status: str = Status.LIVE.value
    created_by: str = ""
    ended_at: Optional[datetime] = None
    remaining_budget: float = 0.0
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
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
            ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
            remaining_budget=row['remaining_budget'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

@dataclass
class Submission:
    id: Optional[int] = None
    discord_id: str = ""
    campaign_id: int = 0
    social_profile_id: int = 0
    video_url: str = ""
    normalized_video_id: str = ""
    platform: str = ""
    starting_views: int = 0
    current_views: int = 0
    earnings: float = 0.0
    status: str = Status.PENDING.value
    tracking: bool = False
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    message_id: Optional[str] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            discord_id=row['discord_id'],
            campaign_id=row['campaign_id'],
            social_profile_id=row['social_profile_id'],
            video_url=row['video_url'],
            normalized_video_id=row['normalized_video_id'],
            platform=row['platform'],
            starting_views=row['starting_views'],
            current_views=row['current_views'],
            earnings=row['earnings'],
            status=row['status'],
            tracking=bool(row['tracking']),
            submitted_at=datetime.fromisoformat(row['submitted_at']) if row['submitted_at'] else None,
            approved_at=datetime.fromisoformat(row['approved_at']) if row['approved_at'] else None,
            approved_by=row['approved_by'],
            message_id=row['message_id']
        )

@dataclass
class BannedProfile:
    id: Optional[int] = None
    platform: str = ""
    profile_url: str = ""
    normalized_id: str = ""
    reason: str = ""
    banned_by: str = ""
    banned_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            platform=row['platform'],
            profile_url=row['profile_url'],
            normalized_id=row['normalized_id'],
            reason=row['reason'],
            banned_by=row['banned_by'],
            banned_at=datetime.fromisoformat(row['banned_at']) if row['banned_at'] else None
        )

@dataclass
class Payout:
    id: Optional[int] = None
    discord_id: str = ""
    campaign_id: int = 0
    amount: float = 0.0
    status: str = Status.PENDING.value
    usdt_tx_hash: Optional[str] = None
    paid_by: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            discord_id=row['discord_id'],
            campaign_id=row['campaign_id'],
            amount=row['amount'],
            status=row['status'],
            usdt_tx_hash=row['usdt_tx_hash'],
            paid_by=row['paid_by'],
            paid_at=datetime.fromisoformat(row['paid_at']) if row['paid_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
  )
