import discord
from discord.ext import commands

from services.database_service import DatabaseService
from views.modal_views import RejectSubmissionModal, BanProfileModal, RejectProfileModal

db_service = DatabaseService()

class InteractionHandlers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions"""
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get('custom_id', '')
        
        if custom_id.startswith('approve_submission:'):
            await self.approve_submission(interaction, custom_id)
        elif custom_id.startswith('reject_submission:'):
            await self.reject_submission_modal(interaction, custom_id)
        elif custom_id.startswith('ban_profile:'):
            await self.ban_profile_modal(interaction, custom_id)
            
    async def approve_submission(self, interaction: discord.Interaction, custom_id: str):
        """Approve a submission"""
        submission_id = int(custom_id.split(':')[1])
        
        try:
            # Get submission
            submission = await db_service.get_submission_by_id(submission_id)
            if not submission:
                await interaction.response.send_message(
                    "❌ Submission not found.",
                    ephemeral=True
                )
                return
                
            # Approve submission
            await db_service.approve_submission(
                submission_id=submission_id,
                approved_by=str(interaction.user.id)
            )
            
            # Update message in submission channel
            if submission.message_id and self.bot.submission_channel:
                try:
                    message = await self.bot.submission_channel.fetch_message(int(submission.message_id))
                    
                    embed = message.embeds[0]
                    embed.title = "✅ Approved Submission"
                    embed.color = discord.Color.green()
                    embed.add_field(
                        name="Approved By",
                        value=f"<@{interaction.user.id}>",
                        inline=True
                    )
                    embed.add_field(
                        name="Approved At",
                        value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>",
                        inline=True
                    )
                    
                    await message.edit(embed=embed, view=None)
                    
                except Exception as e:
                    print(f"Failed to update submission message: {e}")
                    
            await interaction.response.send_message(
                f"✅ Submission #{submission_id} approved. Tracking started.",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='SUBMISSION_APPROVED',
                performed_by=str(interaction.user.id),
                target_user=submission.discord_id,
                details={'submission_id': submission_id}
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while approving submission.",
                ephemeral=True
            )
            raise
            
    async def reject_submission_modal(self, interaction: discord.Interaction, custom_id: str):
        """Show modal for rejection reason"""
        submission_id = int(custom_id.split(':')[1])
        
        modal = RejectSubmissionModal(submission_id)
        await interaction.response.send_modal(modal)
        
    async def ban_profile_modal(self, interaction: discord.Interaction, custom_id: str):
        """Show modal for ban reason"""
        profile_id = int(custom_id.split(':')[1])
        
        modal = BanProfileModal(profile_id)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(InteractionHandlers(bot))
