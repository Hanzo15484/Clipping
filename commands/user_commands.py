import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PermissionManager
from services.database_service import DatabaseService
from utils.validators import Validator
from utils.normalizers import Normalizer

db_service = DatabaseService()

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service
        
    async def ensure_user_exists(self, discord_id: str, username: str):
        """Ensure user exists in database"""
        try:
            user = await self.db_service.get_user(discord_id)
            if not user:
                await self.db_service.create_user_if_not_exists(discord_id, username)
                return await self.db_service.get_user(discord_id)
            return user
        except Exception as e:
            print(f"Error ensuring user exists: {e}")
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
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
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
            logger = logging.getLogger(__name__)
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
            active_campaigns = await self.db_service.get_user_active_campaigns(str(interaction.user.id))
            
            embed = discord.Embed(
                title="📊 Your Statistics",
                description=f"<@{interaction.user.id}>",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Safely get stats
            total_submissions = stats.get('total_submissions', 0)
            approved_submissions = stats.get('approved_submissions', 0)
            campaigns_participated = stats.get('campaigns_participated', 0)
            total_views = stats.get('total_views', 0)
            total_earned = stats.get('total_earned', 0.0)
            last_submission = stats.get('last_submission')
            
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
            
            if last_submission:
                try:
                    embed.add_field(
                        name="⏰ Last Submission",
                        value=f"<t:{int(last_submission.timestamp())}:R>",
                        inline=True
                    )
                except:
                    pass
                
            if active_campaigns:
                try:
                    campaign_text = ", ".join([c['name'] for c in active_campaigns])
                    embed.add_field(name="Active Campaigns", value=campaign_text)
                except:
                    pass
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in my_stats: {str(e)}")
            await interaction.followup.send(
                "❌ An error occurred while fetching your statistics. Please try again.",
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
                
            # Check profile
            profile_data = await self.db_service.get_profile_by_url(user_id, profile)
            if not profile_data or profile_data.status != 'approved':
                await interaction.followup.send(
                    "❌ Profile not found or not approved.",
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
            
            # Post to submission channel if available
            if hasattr(self.bot, 'submission_channel') and self.bot.submission_channel:
                try:
                    embed = discord.Embed(
                        title="📤 New Submission",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    embed.description = f"**Campaign:** {campaign_data.name}\n**Platform:** {profile_data.platform}\n**Video:** {video_url}"
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
                        custom_id=f"ban_profile:{profile_data.id}",
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
                    print(f"Warning: Could not post to submission channel: {e}")
                
            await interaction.followup.send(
                "✅ Submission received! Staff will review it shortly.",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='SUBMISSION_CREATED',
                performed_by=user_id,
                details={
                    'submission_id': submission_id,
                    'campaign': campaign_data.name,
                    'video_url': video_url
                }
            )
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in submit: {str(e)}")
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
            logger = logging.getLogger(__name__)
            logger.error(f"Error in add_payment: {str(e)}")
            await interaction.response.send_message(
                "❌ An error occurred while updating wallet.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
