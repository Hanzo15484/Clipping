import discord
from services.database_service import DatabaseService

db_service = DatabaseService()


class RejectSubmissionModal(discord.ui.Modal):
    def __init__(self, submission_id: int):
        super().__init__(
            title="Reject Submission",
            custom_id=f"reject_submission_modal:{submission_id}"
        )
        self.submission_id = submission_id

        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await db_service.reject_submission(self.submission_id)

        await interaction.response.send_message(
            f"❌ Submission #{self.submission_id} rejected.\n\n"
            f"**Reason:** {self.reason.value}",
            ephemeral=True
        )


class BanProfileModal(discord.ui.Modal):
    def __init__(self, profile_id: int):
        super().__init__(
            title="Ban Profile",
            custom_id=f"ban_profile_modal:{profile_id}"
        )
        self.profile_id = profile_id

        self.reason = discord.ui.TextInput(
            label="Ban reason",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        profile = await db_service.get_profile_by_id(self.profile_id)
        if not profile:
            return await interaction.response.send_message(
                "❌ Profile not found.",
                ephemeral=True
            )

        await db_service.ban_profile(
            platform=profile.platform,
            profile_url=profile.profile_url,
            normalized_id=profile.normalized_id,
            reason=self.reason.value,
            banned_by=str(interaction.user.id)
        )

        await interaction.response.send_message(
            f"🚫 Profile banned:\n{profile.profile_url}",
            ephemeral=True
        )
