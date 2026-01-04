"""import discord
from discord.ext import commands

from services.database_service import DatabaseService

db_service = DatabaseService()

class ModalHandlers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_modal_submit(self, interaction: discord.Interaction):
        """Handle modal submissions"""
        if not interaction.custom_id:
            return
            
        if interaction.custom_id.startswith('reject_submission_modal:'):
            await self.process_rejection(interaction)
        elif interaction.custom_id.startswith('ban_profile_modal:'):
            await self.process_ban(interaction)
        elif interaction.custom_id.startswith('reject_profile_modal:'):
            await self.process_profile_rejection(interaction)
            
    async def process_rejection(self, interaction: discord.Interaction):
        """Process submission rejection"""
        submission_id = int(interaction.custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            # Get submission
            submission = await db_service.get_submission_by_id(submission_id)
            if not submission:
                await interaction.response.send_message(
                    "❌ Submission not found.",
                    ephemeral=True
                )
                return
                
            # Reject submission
            await db_service.reject_submission(submission_id)
            
            # Update message in submission channel
            if submission.message_id and self.bot.submission_channel:
                try:
                    message = await self.bot.submission_channel.fetch_message(int(submission.message_id))
                    
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
                    print(f"Failed to update submission message: {e}")
                    
            await interaction.response.send_message(
                f"✅ Submission #{submission_id} rejected.",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='SUBMISSION_REJECTED',
                performed_by=str(interaction.user.id),
                target_user=submission.discord_id,
                details={
                    'submission_id': submission_id,
                    'reason': reason
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while rejecting submission.",
                ephemeral=True
            )
            raise
            
    async def process_ban(self, interaction: discord.Interaction):
        """Process profile ban"""
        profile_id = int(interaction.custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            # Get profile
            profile = await db_service.get_profile_by_id(profile_id)
            if not profile:
                await interaction.response.send_message(
                    "❌ Profile not found.",
                    ephemeral=True
                )
                return
                
            # Ban profile
            await db_service.ban_profile(
                platform=profile.platform,
                profile_url=profile.profile_url,
                normalized_id=profile.normalized_id,
                reason=reason,
                banned_by=str(interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"✅ Profile banned: {profile.profile_url}",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='PROFILE_BANNED_MODAL',
                performed_by=str(interaction.user.id),
                details={
                    'profile_id': profile_id,
                    'profile_url': profile.profile_url,
                    'reason': reason
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
            raise
            
    async def process_profile_rejection(self, interaction: discord.Interaction):
        """Process profile rejection"""
        profile_id = int(interaction.custom_id.split(':')[1])
        reason = interaction.data['components'][0]['components'][0]['value']
        
        try:
            # Reject profile
            await db_service.reject_profile(profile_id, reason)
            
            await interaction.response.send_message(
                f"✅ Profile #{profile_id} rejected.",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='PROFILE_REJECTED',
                performed_by=str(interaction.user.id),
                details={
                    'profile_id': profile_id,
                    'reason': reason
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while rejecting profile.",
                ephemeral=True
            )
            raise

async def setup(bot):
    await bot.add_cog(ModalHandlers(bot))"""

