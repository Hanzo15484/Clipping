import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional
from discord.ext import tasks

from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class ViewTracker:
    def __init__(self, bot):
        self.bot = bot
        self.db_service = DatabaseService()
        self.tracking_interval = int(os.getenv('TRACKING_INTERVAL_MINUTES', '30'))
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL_HOURS', '24'))
        
    def start_tracking(self):
        """Start background tracking tasks"""
        self.track_views.start()
        self.cleanup_data.start()
        
    def stop_tracking(self):
        """Stop background tracking tasks"""
        self.track_views.stop()
        self.cleanup_data.stop()
        
    @tasks.loop(minutes=30)
    async def track_views(self):
        """Track video views"""
        logger.info("Starting view tracking...")
        
        try:
            submissions = await self.db_service.get_tracking_submissions()
            
            for submission_data in submissions:
                try:
                    # Check stop conditions
                    if submission_data['remaining_budget'] <= 0:
                        await self.db_service.update_submission_tracking(
                            submission_data['id'], False
                        )
                        continue
                        
                    # Get current views
                    current_views = await self.get_video_views(
                        submission_data['video_url'],
                        submission_data['platform']
                    )
                    
                    if current_views is None:
                        continue
                        
                    view_increase = current_views - submission_data['current_views']
                    if view_increase <= 0:
                        continue
                        
                    # Calculate earnings
                    earnings = self.calculate_earnings(
                        view_increase,
                        submission_data['rate_per_100k'],
                        submission_data['rate_per_1m'],
                        submission_data['max_earn_per_post'] - submission_data['earnings']
                    )
                    
                    if earnings <= 0:
                        continue
                        
                    # Check campaign budget
                    if earnings > submission_data['remaining_budget']:
                        await self.db_service.update_campaign_budget(
                            submission_data['campaign_id'], 0
                        )
                        await self.db_service.update_submission_tracking(
                            submission_data['id'], False
                        )
                        continue
                        
                    # Update records
                    await self.db_service.update_submission_views(
                        submission_data['id'],
                        current_views,
                        earnings
                    )
                    
                    await self.db_service.update_campaign_budget(
                        submission_data['campaign_id'],
                        earnings
                    )
                    
                    await self.db_service.update_user_earnings(
                        submission_data['discord_id'],
                        earnings
                    )
                    
                    # Log view history
                    await self.db_service.add_view_history(
                        submission_data['id'],
                        current_views
                    )
                    
                    # Log milestone
                    if current_views >= 100000 or current_views % 10000 == 0:
                        await self.db_service.log_action(
                            'VIEW_MILESTONE',
                            'system',
                            submission_data['discord_id'],
                            {
                                'submission_id': submission_data['id'],
                                'views': current_views,
                                'earnings': earnings
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Error tracking submission {submission_data.get('id')}: {e}")
                    
            logger.info(f"View tracking completed for {len(submissions)} submissions")
            
        except Exception as e:
            logger.error(f"Error in view tracking: {e}")
            await self.db_service.log_action(
                'TRACKING_ERROR',
                'system',
                details={'error': str(e)}
            )
            
    @tasks.loop(hours=24)
    async def cleanup_data(self):
        """Clean up old data"""
        logger.info("Starting data cleanup...")
        
        try:
            # Archive old logs (keep 90 days)
            await self.db_service.cleanup_old_logs(90)
            
            # Archive view history (keep 60 days)
            await self.db_service.cleanup_old_view_history(60)
            
            logger.info("Data cleanup completed")
            
        except Exception as e:
            logger.error(f"Error in data cleanup: {e}")
            
    def calculate_earnings(self, views: int, rate_100k: float, 
                          rate_1m: float, max_earn: float) -> float:
        """Calculate earnings based on views and rates"""
        earnings_per_100k = (views / 100000) * rate_100k
        earnings_per_1m = (views / 1000000) * rate_1m
        earnings = max(earnings_per_100k, earnings_per_1m)
        return min(earnings, max_earn)
        
    async def get_video_views(self, url: str, platform: str) -> Optional[int]:
        """Mock function to get video views"""
        # In production, implement actual API calls
        try:
            # Simulate API call delay
            await asyncio.sleep(0.5)
            
            # Return mock data
            base_views = random.randint(1000, 50000)
            growth = random.randint(100, 1000)
            return base_views + growth
            
        except Exception as e:
            logger.error(f"Error getting video views: {e}")
            return None
            
    async def post_submission_to_channel(self, submission_id: int, campaign, profile,
                                        video_url: str, starting_views: int, user_id: str):
        """Post submission to approval channel"""
        if not self.bot.submission_channel:
            return
            
        try:
            import discord
            
            embed = discord.Embed(
                title="📤 New Submission",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.description = f"**Campaign:** {campaign.name}\n**Platform:** {profile.platform}\n**Video:** {video_url}"
            embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
            embed.add_field(name="Profile", value=profile.profile_url, inline=True)
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
                custom_id=f"ban_profile:{profile.id}",
                label="🚫 Ban Profile",
                style=discord.ButtonStyle.secondary
            ))
            
            admin_role = os.getenv('ADMIN_ROLE', 'Admin')
            message = await self.bot.submission_channel.send(
                content=f"<@&{admin_role}> New submission!",
                embed=embed,
                view=view
            )
            
            # Update submission with message ID
            await self.db_service.update_submission_message_id(
                submission_id,
                str(message.id)
            )
            
        except Exception as e:
            logger.error(f"Failed to post to submission channel: {e}")
