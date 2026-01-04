import discord
from services.database_service import DatabaseService

db_service = DatabaseService()

class RejectSubmissionModal(discord.ui.Modal):
    def __init__(self, submission_id: int):
        super().__init__(title="Reject Submission")
        self.submission_id = submission_id
        
        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="Please provide a reason for rejection..."
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason.value
        
        try:
            # Get submission
            submission = await db_service.get_submission_by_id(self.submission_id)
            if not submission:
                await interaction.followup.send(
                    "❌ Submission not found.",
                    ephemeral=True
                )
                return
                
            # Check if already approved/rejected
            if submission.status != 'pending':
                await interaction.followup.send(
                    f"❌ Submission is already {submission.status}.",
                    ephemeral=True
                )
                return
                
            # Reject submission
            await db_service.reject_submission(self.submission_id, reason)
            
            # Update message in submission channel if bot is available
            if submission.message_id and hasattr(interaction.client, 'submission_channel'):
                try:
                    channel = interaction.client.submission_channel
                    message = await channel.fetch_message(int(submission.message_id))
                    
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
                        value=reason[:1000],
                        inline=False
                    )
                    
                    await message.edit(embed=embed, view=None)
                    
                except Exception as e:
                    print(f"Failed to update submission message: {e}")
                    
            await interaction.followup.send(
                f"✅ Submission #{self.submission_id} rejected.",
                ephemeral=True
            )
            
            # Log action
            await db_service.log_action(
                action_type='SUBMISSION_REJECTED',
                performed_by=str(interaction.user.id),
                target_user=submission.discord_id,
                details={
                    'submission_id': self.submission_id,
                    'reason': reason
                }
            )
            
        except Exception as e:
            print(f"Error rejecting submission: {e}")
            await interaction.followup.send(
                "❌ An error occurred while rejecting submission.",
                ephemeral=True
            )
        
class BanProfileModal(discord.ui.Modal):
    def __init__(self, profile_id: int):
        super().__init__(title="Ban Profile")
        self.profile_id = profile_id
        
        self.reason = discord.ui.TextInput(
            label="Ban reason",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="Why are you banning this profile?"
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason.value
        
        try:
            # Get profile
            profile = await db_service.get_profile_by_id(self.profile_id)
            if not profile:
                await interaction.followup.send(
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
            
            await interaction.followup.send(
                f"✅ Profile banned: {profile.profile_url}",
                ephemeral=True
            )
            
            # Log action
            await db_service.log_action(
                action_type='PROFILE_BANNED_MODAL',
                performed_by=str(interaction.user.id),
                details={
                    'profile_id': self.profile_id,
                    'profile_url': profile.profile_url,
                    'reason': reason
                }
            )
            
        except Exception as e:
            print(f"Error banning profile: {e}")
            await interaction.followup.send(
                "❌ An error occurred while banning profile.",
                ephemeral=True
            )
        
class RejectProfileModal(discord.ui.Modal):
    def __init__(self, profile_id: int):
        super().__init__(title="Reject Profile")
        self.profile_id = profile_id
        
        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="Why are you rejecting this profile?"
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason.value
        
        try:
            # Reject profile
            await db_service.reject_profile(self.profile_id, reason)
            
            await interaction.followup.send(
                f"✅ Profile #{self.profile_id} rejected.",
                ephemeral=True
            )
            
            # Log action
            await db_service.log_action(
                action_type='PROFILE_REJECTED',
                performed_by=str(interaction.user.id),
                details={
                    'profile_id': self.profile_id,
                    'reason': reason
                }
            )
            
        except Exception as e:
            print(f"Error rejecting profile: {e}")
            await interaction.followup.send(
                "❌ An error occurred while rejecting profile.",
                ephemeral=True
            )
