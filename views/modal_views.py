import discord
from services.database_service import DatabaseService

db_service = DatabaseService()

class RejectSubmissionModal(discord.ui.Modal):
    def __init__(self, submission_id: int):
        super().__init__(title="Reject Submission")
        self.submission_id = submission_id
        self.custom_id = f"reject_submission_modal:{submission_id}"
        
        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="rejection_reason"
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        
        # Get submission
        submission = await db_service.get_submission_by_id(self.submission_id)
        if not submission:
            await interaction.response.send_message(
                "❌ Submission not found.",
                ephemeral=True
            )
            return
            
        # Reject submission
        await db_service.reject_submission(self.submission_id)
        
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
        
        await interaction.response.send_message(
            f"✅ Submission #{self.submission_id} rejected.",
            ephemeral=True
        )
        
class BanProfileModal(discord.ui.Modal):
    def __init__(self, profile_id: int):
        super().__init__(title="Ban Profile")
        self.profile_id = profile_id
        self.custom_id = f"ban_profile_modal:{profile_id}"
        
        self.reason = discord.ui.TextInput(
            label="Ban reason",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="ban_reason"
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        
        # Get profile
        profile = await db_service.get_profile_by_id(self.profile_id)
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
                'profile_id': self.profile_id,
                'profile_url': profile.profile_url,
                'reason': reason
            }
        )
        
class RejectProfileModal(discord.ui.Modal):
    def __init__(self, profile_id: int):
        super().__init__(title="Reject Profile")
        self.profile_id = profile_id
        self.custom_id = f"reject_profile_modal:{profile_id}"
        
        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True,
            custom_id="rejection_reason"
        )
        self.add_item(self.reason)
        
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        
        # Reject profile
        await db_service.reject_profile(self.profile_id, reason)
        
        await interaction.response.send_message(
            f"✅ Profile #{self.profile_id} rejected.",
            ephemeral=True
        )
        
        await db_service.log_action(
            action_type='PROFILE_REJECTED',
            performed_by=str(interaction.user.id),
            details={
                'profile_id': self.profile_id,
                'reason': reason
            }
                )
