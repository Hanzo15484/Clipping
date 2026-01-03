import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PermissionManager
from services.database_service import DatabaseService
from utils.validators import Validator
from utils.normalizers import Normalizer
from views.approval_views import ProfileReviewView

db_service = DatabaseService()

class StaffCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service
        
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
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        # Validate URL
        is_valid, error_msg = Validator.validate_profile_url(platform, profile_url)
        if not is_valid:
            await interaction.response.send_message(
                f"❌ {error_msg}",
                ephemeral=True
            )
            return
            
        normalized_id = Normalizer.normalize_profile_id(platform, profile_url)
        if not normalized_id:
            await interaction.response.send_message(
                "❌ Invalid profile URL.",
                ephemeral=True
            )
            return
            
        try:
            # Check global ban
            banned = await self.db_service.get_banned_profile(normalized_id)
            if banned:
                await interaction.response.send_message(
                    f"❌ This profile is banned. Reason: {banned.reason}",
                    ephemeral=True
                )
                return
                
            # Check global uniqueness
            existing = await self.db_service.get_profile_by_normalized_id(normalized_id)
            if existing:
                await interaction.response.send_message(
                    "❌ This profile is already registered to another user.",
                    ephemeral=True
                )
                return
                
            # Ensure user exists
            await self.db_service.create_user_if_not_exists(str(user.id), str(user))
            
            # Add profile
            profile_id = await self.db_service.create_social_profile(
                discord_id=str(user.id),
                platform=platform,
                profile_url=profile_url,
                normalized_id=normalized_id
            )
            
            await interaction.response.send_message(
                f"✅ Profile registered for <@{user.id}>. Status: Pending",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='PROFILE_REGISTERED',
                performed_by=str(interaction.user.id),
                target_user=str(user.id),
                details={
                    'platform': platform,
                    'profile_url': profile_url,
                    'profile_id': profile_id
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while registering profile.",
                ephemeral=True
            )
            raise
            
    @app_commands.command(name="approval-page", description="[Staff] View pending approvals")
    async def approval_page(self, interaction: discord.Interaction):
        """Show approval queue"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get pending items
            pending_profiles = await self.db_service.get_pending_profiles(limit=10)
            pending_submissions = await self.db_service.get_pending_submissions(limit=10)
            
            embed = discord.Embed(
                title="📋 Approval Queue",
                description="Pending items requiring review",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            
            if pending_profiles:
                profile_text = "\n\n".join([
                    f"**{i+1}. {p.platform.upper()}**\nUser: <@{p.discord_id}>\nProfile: {p.profile_url}\nSubmitted: <t:{int(p.created_at.timestamp())}:R>"
                    for i, p in enumerate(pending_profiles)
                ])
                embed.add_field(
                    name=f"📱 Pending Profiles ({len(pending_profiles)})",
                    value=profile_text,
                    inline=False
                )
                
            if pending_submissions:
                submission_text = "\n\n".join([
                    f"**{i+1}. {s['campaign_name']}**\nUser: <@{s['discord_id']}>\nVideo: {s['video_url']}\nViews: {s['starting_views']:,}\nSubmitted: <t:{int(s['submitted_at'].timestamp())}:R>"
                    for i, s in enumerate(pending_submissions)
                ])
                embed.add_field(
                    name=f"📤 Pending Submissions ({len(pending_submissions)})",
                    value=submission_text,
                    inline=False
                )
                
            if not pending_profiles and not pending_submissions:
                embed.description = "✅ No pending items!"
                
            # Create select menu for profiles
            view = None
            if pending_profiles:
                class ProfileSelectView(discord.ui.View):
                    def __init__(self, profiles, bot):
                        super().__init__(timeout=180)  # 3 minute timeout
                        self.profiles = profiles
                        self.bot = bot
                        
                        # Create select menu
                        select = discord.ui.Select(
                            placeholder="Select profile to review",
                            options=[
                                discord.SelectOption(
                                    label=f"{p.platform} - {p.discord_id[:10]}",
                                    description=f"Profile {i+1}",
                                    value=str(p.id)
                                )
                                for i, p in enumerate(profiles)
                            ]
                        )
                        select.callback = self.select_callback
                        self.add_item(select)
                        
                    async def select_callback(self, interaction: discord.Interaction):
                        profile_id = int(self.values[0])
                        profile = await db_service.get_profile_by_id(profile_id)
                        
                        if profile:
                            view = ProfileReviewView(profile_id)
                            embed = discord.Embed(
                                title="👤 Profile Review",
                                color=discord.Color.blue(),
                                timestamp=discord.utils.utcnow()
                            )
                            embed.add_field(name="User", value=f"<@{profile.discord_id}>", inline=True)
                            embed.add_field(name="Platform", value=profile.platform, inline=True)
                            embed.add_field(name="Profile URL", value=profile.profile_url, inline=False)
                            embed.add_field(name="Status", value=profile.status, inline=True)
                            
                            await interaction.response.send_message(
                                embed=embed,
                                view=view,
                                ephemeral=True
                            )
                
                view = ProfileSelectView(pending_profiles, self.bot)
                
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while fetching approval queue.",
                ephemeral=True
            )
            raise
            
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
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        normalized_id = Normalizer.normalize_profile_id(platform, profile_url)
        if not normalized_id:
            await interaction.response.send_message(
                "❌ Invalid profile URL.",
                ephemeral=True
            )
            return
            
        try:
            # Check if already banned
            existing = await self.db_service.get_banned_profile(normalized_id)
            if existing:
                await interaction.response.send_message(
                    "❌ Profile is already banned.",
                    ephemeral=True
                )
                return
                
            # Ban profile
            await self.db_service.ban_profile(
                platform=platform,
                profile_url=profile_url,
                normalized_id=normalized_id,
                reason=reason,
                banned_by=str(interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"✅ Profile banned: {profile_url}",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='PROFILE_BANNED',
                performed_by=str(interaction.user.id),
                details={
                    'platform': platform,
                    'profile_url': profile_url,
                    'reason': reason
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
            raise
            
    @app_commands.command(name="ban-list", description="[Staff] List banned profiles")
    async def ban_list(self, interaction: discord.Interaction):
        """List banned profiles"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            banned_profiles = await self.db_service.get_banned_profiles(limit=20)
            
            if not banned_profiles:
                await interaction.followup.send(
                    "No banned profiles.",
                    ephemeral=True
                )
                return
                
            embed = discord.Embed(
                title="🚫 Banned Profiles",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            for i, ban in enumerate(banned_profiles):
                embed.add_field(
                    name=f"{i+1}. {ban.platform.upper()}",
                    value=f"**Profile:** {ban.profile_url}\n**Reason:** {ban.reason}\n**Banned by:** <@{ban.banned_by}>\n**Date:** <t:{int(ban.banned_at.timestamp())}:R>",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while fetching banned profiles.",
                ephemeral=True
            )
            raise

async def setup(bot):
    await bot.add_cog(StaffCommands(bot))
