import discord
from discord.ext import commands

from services.database_service import DatabaseService
from views.modal_views import RejectSubmissionModal, BanProfileModal

db_service = DatabaseService()


class InteractionHandlers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Only handle component interactions (buttons)
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        if not custom_id:
            return

        if custom_id.startswith("approve_submission:"):
            await self.approve_submission(interaction, custom_id)
            return

        if custom_id.startswith("reject_submission:"):
            await self.reject_submission_modal(interaction, custom_id)
            return

        if custom_id.startswith("ban_profile:"):
            await self.ban_profile_modal(interaction, custom_id)
            return

    async def approve_submission(self, interaction: discord.Interaction, custom_id: str):
        # ✅ ACK FIRST (MOST IMPORTANT)
        await interaction.response.defer(ephemeral=True)

        submission_id = int(custom_id.split(":")[1])

        submission = await db_service.get_submission_by_id(submission_id)
        if not submission:
            return await interaction.followup.send(
                "❌ Submission not found.",
                ephemeral=True
            )

        await db_service.approve_submission(
            submission_id=submission_id,
            approved_by=str(interaction.user.id)
        )

        # Update submission message embed
        if submission.message_id and self.bot.submission_channel:
            try:
                message = await self.bot.submission_channel.fetch_message(
                    int(submission.message_id)
                )

                embed = message.embeds[0]
                embed.title = "✅ Approved Submission"
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Approved By",
                    value=f"<@{interaction.user.id}>",
                    inline=True
                )

                await message.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Failed to update submission message: {e}")

        await interaction.followup.send(
            f"✅ Submission #{submission_id} approved.",
            ephemeral=True
        )

    async def reject_submission_modal(self, interaction: discord.Interaction, custom_id: str):
        submission_id = int(custom_id.split(":")[1])
        modal = RejectSubmissionModal(submission_id)
        await interaction.response.send_modal(modal)

    async def ban_profile_modal(self, interaction: discord.Interaction, custom_id: str):
        profile_id = int(custom_id.split(":")[1])
        modal = BanProfileModal(profile_id)
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(InteractionHandlers(bot))
