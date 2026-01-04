import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PermissionManager
from services.database_service import DatabaseService
from utils.validators import Validator
from utils.normalizers import Normalizer

logger = logging.getLogger(__name__)
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
            logger.error(f"Error in register: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while registering profile.",
                ephemeral=True
            )
            
    @app_commands.command(name="approval-page", description="[Staff] View pending approvals")
    async def approval_page(self, interaction: discord.Interaction):
        """Show approval queue with working buttons"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get pending items
            pending_profiles = await self.db_service.get_pending_profiles(limit=10)
            
            if not pending_profiles:
                await interaction.followup.send(
                    "✅ No pending profiles to approve.",
                    ephemeral=True
                )
                return
                
            # Send each profile separately with its own buttons
            for i, profile in enumerate(pending_profiles):
                # Get Discord user for display
                try:
                    discord_user = await self.bot.fetch_user(int(profile.discord_id))
                    username = discord_user.name
                except:
                    username = profile.discord_id
                
                embed = discord.Embed(
                    title=f"📋 Profile Approval #{i+1}",
                    color=discord.Color.yellow()
                )
                embed.add_field(name="Platform", value=profile.platform.upper(), inline=True)
                embed.add_field(name="User", value=f"<@{profile.discord_id}> ({username})", inline=True)
                embed.add_field(name="Profile URL", value=profile.profile_url, inline=False)
                embed.add_field(name="Profile ID", value=f"`{profile.id}`", inline=True)
                embed.add_field(name="Status", value=profile.status, inline=True)
                
                # Create view with buttons
                view = discord.ui.View(timeout=300)  # 5 minute timeout
                
                # Approve button
                approve_button = discord.ui.Button(
                    label="✅ Approve",
                    style=discord.ButtonStyle.success,
                    custom_id=f"approve_profile_{profile.id}"
                )
                
                async def approve_callback(interaction: discord.Interaction, pid=profile.id):
                    try:
                        # Approve the profile
                        await self.db_service.approve_profile(pid, str(interaction.user.id))
                        
                        # Update the message
                        embed = discord.Embed(
                            title="✅ Profile Approved",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Approved by", value=f"<@{interaction.user.id}>", inline=True)
                        embed.add_field(name="Profile ID", value=f"`{pid}`", inline=True)
                        embed.add_field(name="Status", value="Approved ✅", inline=True)
                        
                        # Disable buttons
                        for child in view.children:
                            child.disabled = True
                        
                        await interaction.response.edit_message(embed=embed, view=view)
                        
                        # Send confirmation
                        await interaction.followup.send(
                            f"✅ Profile `{pid}` has been approved successfully!",
                            ephemeral=True
                        )
                        
                        logger.info(f"Profile {pid} approved by {interaction.user.id}")
                        
                    except Exception as e:
                        logger.error(f"Error approving profile: {e}")
                        await interaction.response.send_message(
                            "❌ Error approving profile. Please try again.",
                            ephemeral=True
                        )
                
                approve_button.callback = approve_callback
                view.add_item(approve_button)
                
                # Reject button
                reject_button = discord.ui.Button(
                    label="❌ Reject",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"reject_profile_{profile.id}"
                )
                
                async def reject_callback(interaction: discord.Interaction, pid=profile.id):
                    # Create modal for rejection reason
                    modal = discord.ui.Modal(title=f"Reject Profile #{pid}")
                    
                    reason_input = discord.ui.TextInput(
                        label="Reason for rejection",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter rejection reason...",
                        required=True,
                        max_length=500,
                        custom_id="rejection_reason"
                    )
                    modal.add_item(reason_input)
                    
                    async def modal_submit(interaction: discord.Interaction):
                        reason = reason_input.value
                        try:
                            # Reject the profile
                            await self.db_service.reject_profile(pid, reason)
                            
                            # Update the message
                            embed = discord.Embed(
                                title="❌ Profile Rejected",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="Rejected by", value=f"<@{interaction.user.id}>", inline=True)
                            embed.add_field(name="Profile ID", value=f"`{pid}`", inline=True)
                            embed.add_field(name="Reason", value=reason, inline=False)
                            
                            # Disable buttons
                            for child in view.children:
                                child.disabled = True
                            
                            await interaction.response.edit_message(embed=embed, view=view)
                            
                            # Send confirmation
                            await interaction.followup.send(
                                f"✅ Profile `{pid}` has been rejected.",
                                ephemeral=True
                            )
                            
                            logger.info(f"Profile {pid} rejected by {interaction.user.id}")
                            
                        except Exception as e:
                            logger.error(f"Error rejecting profile: {e}")
                            await interaction.response.send_message(
                                "❌ Error rejecting profile.",
                                ephemeral=True
                            )
                    
                    modal.on_submit = modal_submit
                    await interaction.response.send_modal(modal)
                
                reject_button.callback = reject_callback
                view.add_item(reject_button)
                
                # Ban button
                ban_button = discord.ui.Button(
                    label="🚫 Ban",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"ban_profile_{profile.id}"
                )
                
                async def ban_callback(interaction: discord.Interaction, pid=profile.id, purl=profile.profile_url, pplat=profile.platform):
                    # Create modal for ban reason
                    modal = discord.ui.Modal(title=f"Ban Profile #{pid}")
                    
                    reason_input = discord.ui.TextInput(
                        label="Ban reason",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter ban reason...",
                        required=True,
                        max_length=500,
                        custom_id="ban_reason"
                    )
                    modal.add_item(reason_input)
                    
                    async def modal_submit(interaction: discord.Interaction):
                        reason = reason_input.value
                        try:
                            # Get normalized ID
                            normalized_id = Normalizer.normalize_profile_id(pplat, purl)
                            if normalized_id:
                                # Ban the profile
                                await self.db_service.ban_profile(
                                    platform=pplat,
                                    profile_url=purl,
                                    normalized_id=normalized_id,
                                    reason=reason,
                                    banned_by=str(interaction.user.id)
                                )
                                
                                # Update the message
                                embed = discord.Embed(
                                    title="🚫 Profile Banned",
                                    color=discord.Color.dark_red()
                                )
                                embed.add_field(name="Banned by", value=f"<@{interaction.user.id}>", inline=True)
                                embed.add_field(name="Profile ID", value=f"`{pid}`", inline=True)
                                embed.add_field(name="Reason", value=reason, inline=False)
                                
                                # Disable buttons
                                for child in view.children:
                                    child.disabled = True
                                
                                await interaction.response.edit_message(embed=embed, view=view)
                                
                                # Send confirmation
                                await interaction.followup.send(
                                    f"✅ Profile `{pid}` has been banned globally.",
                                    ephemeral=True
                                )
                                
                                logger.info(f"Profile {pid} banned by {interaction.user.id}")
                            else:
                                await interaction.response.send_message(
                                    "❌ Error: Could not normalize profile ID.",
                                    ephemeral=True
                                )
                                
                        except Exception as e:
                            logger.error(f"Error banning profile: {e}")
                            await interaction.response.send_message(
                                "❌ Error banning profile.",
                                ephemeral=True
                            )
                    
                    modal.on_submit = modal_submit
                    await interaction.response.send_modal(modal)
                
                ban_button.callback = ban_callback
                view.add_item(ban_button)
                
                # Send the embed with buttons
                if i == 0:
                    # First message
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                else:
                    # Additional messages
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
            # Send summary
            summary_embed = discord.Embed(
                title="📊 Summary",
                description=f"Showing {len(pending_profiles)} pending profile(s)",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=summary_embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in approval_page: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching approval queue.",
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
            logger.error(f"Error in ban_social: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
            
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
                color=discord.Color.red()
            )
            
            for i, ban in enumerate(banned_profiles):
                embed.add_field(
                    name=f"{i+1}. {ban.platform.upper()}",
                    value=f"**Profile:** {ban.profile_url}\n**Reason:** {ban.reason}\n**Banned by:** <@{ban.banned_by}>",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in ban_list: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching banned profiles.",
                ephemeral=True
            )
    
    @app_commands.command(name="check-profile", description="[Staff] Check profile status")
    @app_commands.describe(profile_url="Profile URL to check")
    async def check_profile(self, interaction: discord.Interaction, profile_url: str):
        """Check if a profile exists and its status"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Try to find profile by URL
            profiles = []
            for platform in ['instagram', 'tiktok', 'youtube']:
                normalized_id = Normalizer.normalize_profile_id(platform, profile_url)
                if normalized_id:
                    profile = await self.db_service.get_profile_by_normalized_id(normalized_id)
                    if profile:
                        profiles.append(profile)
            
            if not profiles:
                await interaction.followup.send(
                    f"❌ No profile found with URL: {profile_url}",
                    ephemeral=True
                )
                return
                
            for profile in profiles:
                embed = discord.Embed(
                    title="🔍 Profile Status Check",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Platform", value=profile.platform.upper(), inline=True)
                embed.add_field(name="User", value=f"<@{profile.discord_id}>", inline=True)
                embed.add_field(name="Profile URL", value=profile.profile_url, inline=False)
                embed.add_field(name="Status", value=profile.status, inline=True)
                embed.add_field(name="Profile ID", value=f"`{profile.id}`", inline=True)
                embed.add_field(name="Normalized ID", value=f"`{profile.normalized_id}`", inline=False)
                
                if profile.status == 'approved':
                    embed.color = discord.Color.green()
                elif profile.status == 'banned':
                    embed.color = discord.Color.red()
                elif profile.status == 'rejected':
                    embed.color = discord.Color.orange()
                else:
                    embed.color = discord.Color.yellow()
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in check_profile: {e}")
            await interaction.followup.send(
                "❌ An error occurred while checking profile.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(StaffCommands(bot))
