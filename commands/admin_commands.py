import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PermissionManager
from services.database_service import DatabaseService
from services.campaign_service import CampaignService

db_service = DatabaseService()
campaign_service = CampaignService()

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service
        self.campaign_service = campaign_service
        
    @app_commands.command(name="ban-remove", description="[Admin] Remove ban from profile")
    @app_commands.describe(profile_id="Banned profile ID")
    async def ban_remove(self, interaction: discord.Interaction, profile_id: str):
        """Remove ban from profile"""
        if not await PermissionManager.enforce_permission(interaction, 'admin'):
            return
            
        try:
            ban = await self.db_service.get_ban_by_id(int(profile_id))
            if not ban:
                await interaction.response.send_message(
                    "❌ Ban record not found.",
                    ephemeral=True
                )
                return
                
            # Remove ban
            await self.db_service.remove_ban(ban.normalized_id)
            
            await interaction.response.send_message(
                f"✅ Ban removed for profile: {ban.profile_url}\nNote: Profile not auto-approved.",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='BAN_REMOVED',
                performed_by=str(interaction.user.id),
                details={
                    'profile_url': ban.profile_url,
                    'platform': ban.platform
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while removing ban.",
                ephemeral=True
            )
            raise
            
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
        if not await PermissionManager.enforce_permission(interaction, 'admin'):
            return
            
        try:
            # Create campaign
            campaign_id = await self.campaign_service.create_campaign(
                name=name,
                platform=platform,
                total_budget=total_budget,
                rate_per_100k=rate_100k,
                rate_per_1m=rate_1m,
                min_views=min_views,
                min_followers=min_followers,
                max_earn_per_creator=max_earn_creator,
                max_earn_per_post=max_earn_post,
                created_by=str(interaction.user.id)
            )
            
            await interaction.response.send_message(
                f'✅ Campaign "{name}" created successfully!',
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='CAMPAIGN_CREATED',
                performed_by=str(interaction.user.id),
                details={
                    'campaign_name': name,
                    'platform': platform,
                    'budget': total_budget,
                    'campaign_id': campaign_id
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while creating campaign: {str(e)}",
                ephemeral=True
            )
            
    # Separate autocomplete function
    async def campaign_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for campaign names"""
        try:
            campaigns = await self.campaign_service.search_live_campaigns(current)
            return [
                app_commands.Choice(name=campaign.name, value=campaign.name)
                for campaign in campaigns[:10]
            ]
        except:
            return []
            
    @app_commands.command(name="campaign-end", description="[Admin] End a campaign")
    @app_commands.describe(campaign="Campaign name")
    @app_commands.autocomplete(campaign=campaign_autocomplete)
    async def campaign_end(self, interaction: discord.Interaction, campaign: str):
        """End a campaign"""
        if not await PermissionManager.enforce_permission(interaction, 'admin'):
            return
            
        try:
            # End campaign
            await self.campaign_service.end_campaign(
                campaign_name=campaign,
                ended_by=str(interaction.user.id)
            )
            
            await interaction.response.send_message(
                f'✅ Campaign "{campaign}" ended successfully.',
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='CAMPAIGN_ENDED',
                performed_by=str(interaction.user.id),
                details={'campaign_name': campaign}
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred while ending campaign: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
