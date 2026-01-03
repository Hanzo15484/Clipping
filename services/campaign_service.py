from typing import List, Optional
from datetime import datetime

from services.database_service import DatabaseService
from models import Campaign

db_service = DatabaseService()

class CampaignService:
    
    async def create_campaign(self, name: str, platform: str, total_budget: float,
                            rate_per_100k: float, rate_per_1m: float, min_views: int,
                            min_followers: int, max_earn_per_creator: float,
                            max_earn_per_post: float, created_by: str) -> int:
        """Create a new campaign"""
        # Check if campaign exists
        existing = await db_service.get_campaign_by_name(name)
        if existing:
            raise ValueError(f"Campaign '{name}' already exists")
            
        # Create campaign
        db_service.database.execute('''
            INSERT INTO campaigns 
            (name, platform, total_budget, rate_per_100k, rate_per_1m, 
             min_views, min_followers, max_earn_per_creator, max_earn_per_post,
             created_by, remaining_budget)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, platform, total_budget, rate_per_100k, rate_per_1m,
            min_views, min_followers, max_earn_per_creator, max_earn_per_post,
            created_by, total_budget
        ))
        
        return db_service.database.get_lastrowid()
        
    async def get_all_campaigns(self) -> List[Campaign]:
        """Get all campaigns"""
        rows = db_service.database.fetch_all('''
            SELECT * FROM campaigns 
            ORDER BY 
                CASE status 
                    WHEN 'live' THEN 1 
                    ELSE 2 
                END,
                created_at DESC
        ''')
        return [Campaign.from_row(row) for row in rows]
        
    async def search_live_campaigns(self, search_term: str) -> List[Campaign]:
        """Search live campaigns"""
        rows = db_service.database.fetch_all('''
            SELECT * FROM campaigns 
            WHERE status = 'live' AND name LIKE ?
            LIMIT 10
        ''', (f'%{search_term}%',))
        return [Campaign.from_row(row) for row in rows]
        
    async def end_campaign(self, campaign_name: str, ended_by: str):
        """End a campaign"""
        campaign = await db_service.get_campaign_by_name(campaign_name)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_name}' not found")
            
        if campaign.status != 'live':
            raise ValueError(f"Campaign '{campaign_name}' is not live")
            
        # Update campaign status
        db_service.database.execute('''
            UPDATE campaigns 
            SET status = 'ended', ended_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), campaign.id))
        
        # Stop tracking all submissions
        db_service.database.execute(
            "UPDATE submissions SET tracking = FALSE WHERE campaign_id = ?",
            (campaign.id,)
        )
