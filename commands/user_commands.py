import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse

from utils.permissions import PermissionManager
from services.database_service import DatabaseService
from utils.validators import Validator
from utils.normalizers import Normalizer

logger = logging.getLogger(__name__)
db_service = DatabaseService()

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service

    @app_commands.command(name="register", description="Register a social profile")
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
            
    def clean_profile_url(self, url: str) -> str:
        """Clean profile URL for comparison"""
        if not url:
            return ""
        
        # Remove protocol
        url = url.lower().replace('https://', '').replace('http://', '')
        
        # Remove www.
        if url.startswith('www.'):
            url = url[4:]
        
        # Parse URL to handle query parameters consistently
        try:
            # Split into base and query
            if '?' in url:
                base, query = url.split('?', 1)
                # Parse query parameters
                params = urllib.parse.parse_qs(query)
                # Sort parameters alphabetically
                sorted_params = sorted(params.items())
                # Rebuild query string
                query = '&'.join([f'{k}={v[0]}' for k, v in sorted_params])
                url = f"{base}?{query}"
            else:
                url = url.rstrip('/')
        except:
            # If parsing fails, just use the URL as-is
            url = url.rstrip('/')
        
        return url
        
    async def ensure_user_exists(self, discord_id: str, username: str):
        """Ensure user exists in database"""
        try:
            user = await self.db_service.get_user(discord_id)
            if not user:
                await self.db_service.create_user_if_not_exists(discord_id, username)
                return await self.db_service.get_user(discord_id)
            return user
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            # Create user anyway
            await self.db_service.create_user_if_not_exists(discord_id, username)
            return await self.db_service.get_user(discord_id)
        
    @app_commands.command(name="my-profile", description="View your profile information")
    async def my_profile(self, interaction: discord.Interaction):
        """Display user profile"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Ensure user exists
            user = await self.ensure_user_exists(
                str(interaction.user.id), 
                str(interaction.user)
            )
            
            if not user:
                await interaction.followup.send(
                    "❌ Could not create or retrieve your profile. Please try again.",
                    ephemeral=True
                )
                return
                
            profiles = await self.db_service.get_user_profiles(str(interaction.user.id))
            
            embed = discord.Embed(
                title="👤 Your Profile",
                description=f"Discord: <@{interaction.user.id}>",
                color=discord.Color.green()
            )
            
            # Get user stats safely
            try:
                stats = await self.db_service.get_user_stats(str(interaction.user.id))
                total_submissions = stats.get('total_submissions', 0)
                approved_submissions = stats.get('approved_submissions', 0)
                total_earned = stats.get('total_earned', 0.0)
            except:
                total_submissions = 0
                approved_submissions = 0
                total_earned = 0.0
            
            embed.add_field(
                name="📊 Statistics",
                value=f"Submissions: {total_submissions}\nApproved: {approved_submissions}\nTotal Earned: ${total_earned:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="💰 Earnings",
                value=f"Paid: ${user.paid_earnings:.2f}\nPending: ${user.pending_earnings:.2f}\nTotal: ${user.total_earnings:.2f}",
                inline=True
            )
            
            wallet_display = f"`{user.usdt_wallet}`" if user.usdt_wallet else "Not set"
            embed.add_field(
                name="💳 Wallet",
                value=wallet_display,
                inline=False
            )
            
            if profiles:
                profile_text = "\n".join([
                    f"**{p.platform.upper()}**: {p.profile_url}\nStatus: {p.status} | Followers: {p.followers:,}"
                    for p in profiles
                ])
                embed.add_field(name="📱 Social Profiles", value=profile_text, inline=False)
            else:
                embed.add_field(name="📱 Social Profiles", value="No profiles registered yet.", inline=False)
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in my_profile: {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your profile. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="my-stats", description="View your statistics and earnings")
    async def my_stats(self, interaction: discord.Interaction):
        """Display user statistics"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Ensure user exists
            user = await self.ensure_user_exists(
                str(interaction.user.id), 
                str(interaction.user)
            )
            
            if not user:
                await interaction.followup.send(
                    "❌ Could not create or retrieve your profile. Please try again.",
                    ephemeral=True
                )
                return
            
            stats = await self.db_service.get_user_stats(str(interaction.user.id))
            
            embed = discord.Embed(
                title="📊 Your Statistics",
                description=f"<@{interaction.user.id}>",
                color=discord.Color.green()
            )
            
            # Safely get stats
            total_submissions = stats.get('total_submissions', 0)
            approved_submissions = stats.get('approved_submissions', 0)
            campaigns_participated = stats.get('campaigns_participated', 0)
            total_views = stats.get('total_views', 0)
            total_earned = stats.get('total_earned', 0.0)
            
            embed.add_field(
                name="📤 Submissions",
                value=f"Total: {total_submissions}\nApproved: {approved_submissions}",
                inline=True
            )
            
            embed.add_field(
                name="👁️ Views",
                value=f"{total_views:,}",
                inline=True
            )
            
            embed.add_field(
                name="💰 Earnings",
                value=f"${total_earned:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="🎯 Campaigns",
                value=f"{campaigns_participated} participated",
                inline=False
            )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in my_stats: {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your statistics. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="submit", description="Submit a video for a campaign")
    async def submit(self, interaction: discord.Interaction):
        """Submit a video for approval - shows dropdowns"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            
            # Ensure user exists
            user = await self.ensure_user_exists(user_id, str(interaction.user))
            if not user:
                await interaction.followup.send(
                    "❌ Could not create or retrieve your profile. Please try again.",
                    ephemeral=True
                )
                return
            
            # Get user's approved profiles
            profiles = await self.db_service.get_user_profiles(user_id)
            approved_profiles = [p for p in profiles if p.status == 'approved']
            
            if not approved_profiles:
                await interaction.followup.send(
                    "❌ You don't have any approved social profiles. Please register and get approval first.",
                    ephemeral=True
                )
                return
            
            # Get active campaigns
            # For now, let's create a simple dropdown or show options
            embed = discord.Embed(
                title="📤 Submit Video",
                description="To submit a video, use the command with parameters:",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Usage",
                value="`/submit-video campaign:<name> profile:<url> video_url:<link>`",
                inline=False
            )
            
            embed.add_field(
                name="Your Approved Profiles",
                value="\n".join([f"• {p.platform.upper()}: `{p.profile_url}`" for p in approved_profiles]),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in submit (interactive): {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="submit-video", description="Submit a video (detailed)")
    @app_commands.describe(
        campaign="Campaign name",
        profile="Your approved profile URL",
        video_url="Video link to submit"
    )
    async def submit_video(self, interaction: discord.Interaction, 
                          campaign: str, profile: str, video_url: str):
        """Submit a video for approval"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            
            # Ensure user exists
            user = await self.ensure_user_exists(user_id, str(interaction.user))
            if not user:
                await interaction.followup.send(
                    "❌ Could not create or retrieve your profile. Please try again.",
                    ephemeral=True
                )
                return
                
            # Check campaign
            campaign_data = await self.db_service.get_campaign_by_name(campaign)
            if not campaign_data or campaign_data.status != 'live':
                await interaction.followup.send(
                    "❌ Campaign not found or not live.",
                    ephemeral=True
                )
                return
                
            # Get all user profiles
            profiles = await self.db_service.get_user_profiles(user_id)
            profile_data = None
            
            # Clean the input profile URL
            cleaned_input = self.clean_profile_url(profile)
            logger.info(f"Looking for profile. Input cleaned: {cleaned_input}")
            
            for p in profiles:
                # Clean stored profile URL
                cleaned_stored = self.clean_profile_url(p.profile_url)
                logger.info(f"Checking against stored: {cleaned_stored}")
                
                if cleaned_input == cleaned_stored:
                    profile_data = p
                    logger.info(f"Found match! Profile ID: {p.id}, Status: {p.status}")
                    break
            
            if not profile_data:
                # Try partial match (just the username part)
                for p in profiles:
                    stored_url = p.profile_url.lower()
                    input_url = profile.lower()
                    
                    # Extract username from URLs
                    import re
                    stored_username = None
                    input_username = None
                    
                    if 'instagram.com/' in stored_url:
                        match = re.search(r'instagram\.com/([^/?]+)', stored_url)
                        if match:
                            stored_username = match.group(1)
                    
                    if 'instagram.com/' in input_url:
                        match = re.search(r'instagram\.com/([^/?]+)', input_url)
                        if match:
                            input_username = match.group(1)
                    
                    if stored_username and input_username and stored_username == input_username:
                        profile_data = p
                        logger.info(f"Found username match! Profile ID: {p.id}")
                        break
                
                if not profile_data:
                    # Show all available profiles for debugging
                    profile_list = "\n".join([
                        f"• {p.platform}: {p.profile_url} (Status: {p.status})"
                        for p in profiles
                    ])
                    
                    debug_info = f"""
**Debug Info:**
Input URL (cleaned): `{cleaned_input}`
Your profiles (cleaned):
""" + "\n".join([f"• {p.platform}: `{self.clean_profile_url(p.profile_url)}` (Status: {p.status})" for p in profiles])
                    
                    await interaction.followup.send(
                        f"❌ Profile not found or not approved.\n\n"
                        f"**Make sure to copy the EXACT URL from your profile list:**\n"
                        f"{profile_list}\n\n"
                        f"{debug_info}",
                        ephemeral=True
                    )
                    return
            
            # Check if profile is approved
            if profile_data.status != 'approved':
                await interaction.followup.send(
                    f"❌ Profile found but status is: `{profile_data.status}`. It needs to be `approved`.\n"
                    f"Profile URL: {profile_data.profile_url}",
                    ephemeral=True
                )
                return
                
            # Validate video URL
            is_valid, error_msg = Validator.validate_video_url(profile_data.platform, video_url)
            if not is_valid:
                await interaction.followup.send(
                    f"❌ {error_msg}",
                    ephemeral=True
                )
                return
                
            # Check duplicate video
            normalized_video_id = Normalizer.normalize_video_id(profile_data.platform, video_url)
            existing = await self.db_service.get_submission_by_video_id(normalized_video_id)
            if existing:
                await interaction.followup.send(
                    "❌ This video has already been submitted.",
                    ephemeral=True
                )
                return
                
            # Get starting views (mock)
            starting_views = 1000  # Default value for now
            
            # Create submission
            submission_id = await self.db_service.create_submission(
                discord_id=user_id,
                campaign_id=campaign_data.id,
                social_profile_id=profile_data.id,
                video_url=video_url,
                normalized_video_id=normalized_video_id,
                platform=profile_data.platform,
                starting_views=starting_views
            )
            
            # Create success embed
            success_embed = discord.Embed(
                title="✅ Submission Received!",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Campaign", value=campaign_data.name, inline=True)
            success_embed.add_field(name="Platform", value=profile_data.platform, inline=True)
            success_embed.add_field(name="Video", value=f"[Link]({video_url})", inline=False)
            success_embed.add_field(name="Submission ID", value=f"`#{submission_id}`", inline=True)
            success_embed.add_field(name="Status", value="Pending review", inline=True)
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Post to submission channel if available
            if hasattr(self.bot, 'submission_channel') and self.bot.submission_channel:
                try:
                    channel_embed = discord.Embed(
                        title="📤 New Submission",
                        color=discord.Color.orange()
                    )
                    
                    channel_embed.description = f"**Campaign:** {campaign_data.name}\n**Platform:** {profile_data.platform}\n**Video:** {video_url}"
                    channel_embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
                    channel_embed.add_field(name="Profile", value=profile_data.profile_url, inline=True)
                    channel_embed.add_field(name="Starting Views", value=f"{starting_views:,}", inline=True)
                    channel_embed.add_field(name="Submission ID", value=f"#{submission_id}", inline=True)
                    
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
                        custom_id=f"ban_profile:{profile_data.id}",
                        label="🚫 Ban Profile",
                        style=discord.ButtonStyle.secondary
                    ))
                    
                    admin_role = os.getenv('ADMIN_ROLE', 'Admin')
                    message = await self.bot.submission_channel.send(
                        content=f"<@&{admin_role}> New submission!",
                        embed=channel_embed,
                        view=view
                    )
                    
                    # Update submission with message ID
                    await self.db_service.update_submission_message_id(
                        submission_id,
                        str(message.id)
                    )
                except Exception as e:
                    logger.error(f"Could not post to submission channel: {e}")
                
            await self.db_service.log_action(
                action_type='SUBMISSION_CREATED',
                performed_by=user_id,
                details={
                    'submission_id':submission_id,
                    'campaign': campaign_data.name,
                    'video_url': video_url
                }
            )
        except Exception as e:
            logger.error(f"Error in submit video: {str(e)}")
            await interaction.followup.send(
            "❌ An error occurred while submitting.",
                ephemeral=True
            )

    @app_commands.command(name="add-payment", description="Add/update your USDT wallet address")
    @app_commands.describe(wallet="Your USDT (ERC20) wallet address")
    async def add_payment(self, interaction: discord.Interaction, wallet: str):
        """Add or update USDT wallet"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        # Validate wallet
        if not Validator.validate_usdt_wallet(wallet):
            await interaction.response.send_message(
                "❌ Invalid USDT (ERC20) wallet address.",
                ephemeral=True
            )
            return
            
        try:
            # Ensure user exists
            await self.ensure_user_exists(str(interaction.user.id), str(interaction.user))
            
            await self.db_service.update_user_wallet(str(interaction.user.id), wallet)
            
            await interaction.response.send_message(
                f"✅ Wallet updated: `{wallet}`",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='WALLET_UPDATED',
                performed_by=str(interaction.user.id),
                details={'wallet': wallet}
            )
            
        except Exception as e:
            logger.error(f"Error in add_payment: {str(e)}")
            await interaction.response.send_message(
                "❌ An error occurred while updating wallet.",
                ephemeral=True
            )
    
    @app_commands.command(name="my-profiles", description="View your social profiles")
    async def my_profiles(self, interaction: discord.Interaction):
        """Display user's social profiles"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            profiles = await self.db_service.get_user_profiles(str(interaction.user.id))
            
            if not profiles:
                await interaction.followup.send(
                    "❌ You don't have any registered social profiles.",
                    ephemeral=True
                )
                return
                
            embed = discord.Embed(
                title="📱 Your Social Profiles",
                description=f"<@{interaction.user.id}>",
                color=discord.Color.blue()
            )
            
            for profile in profiles:
                status_emoji = {
                    'pending': '⏳',
                    'approved': '✅',
                    'rejected': '❌',
                    'banned': '🚫'
                }.get(profile.status, '❓')
                
                embed.add_field(
                    name=f"{status_emoji} {profile.platform.upper()}",
                    value=f"**URL:** {profile.profile_url}\n**Status:** {profile.status}\n**Followers:** {profile.followers:,}\n**ID:** `{profile.id}`",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in my_profiles: {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your profiles.",
                ephemeral=True
            )
    
    @app_commands.command(name="test-profile-match", description="Test profile URL matching")
    @app_commands.describe(profile_url="Profile URL to test")
    async def test_profile_match(self, interaction: discord.Interaction, profile_url: str):
        """Test if a profile URL matches your profiles"""
        if not await PermissionManager.enforce_permission(interaction, 'user'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            profiles = await self.db_service.get_user_profiles(str(interaction.user.id))
            
            if not profiles:
                await interaction.followup.send(
                    "❌ You don't have any registered social profiles.",
                    ephemeral=True
                )
                return
            
            cleaned_input = self.clean_profile_url(profile_url)
            
            embed = discord.Embed(
                title="🔍 Profile Matching Test",
                description=f"Testing URL: `{profile_url}`",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Cleaned Input",
                value=f"`{cleaned_input}`",
                inline=False
            )
            
            matches = []
            for p in profiles:
                cleaned_stored = self.clean_profile_url(p.profile_url)
                is_match = cleaned_input == cleaned_stored
                matches.append({
                    'profile': p,
                    'cleaned': cleaned_stored,
                    'match': is_match
                })
                
                embed.add_field(
                    name=f"{p.platform.upper()} - ID: {p.id}",
                    value=f"**Stored:** `{p.profile_url}`\n**Cleaned:** `{cleaned_stored}`\n**Match:** {'✅' if is_match else '❌'}\n**Status:** {p.status}",
                    inline=False
                )
            
            # Check if any match
            any_match = any(m['match'] for m in matches)
            if any_match:
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Result",
                    value="✅ Found matching profile!",
                    inline=False
                )
            else:
                embed.color = discord.Color.red()
                embed.add_field(
                    name="Result",
                    value="❌ No matching profile found.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in test_profile_match: {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred while testing profile match.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(UserCommands(bot))

