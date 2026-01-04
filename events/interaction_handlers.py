import discord
from discord.ext import commands

from services.database_service import DatabaseService
from views.modal_views import (
    RejectSubmissionModal,
    BanProfileModal,
)

db_service = DatabaseService()


# =========================
# 🔘 Submission Review View
# =========================
class SubmissionReviewView(discord.ui.View):
    def __init__(self, submission_id: int, bot: commands.Bot):
        super().__init__(timeout=None)  # persistent
        self.submission_id = submission_id
        self.bot = bot

    # ✅ APPROVE BUTTON
    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        custom_id="approve_submission"
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        submission = await db_service.get_submission_by_id(self.submission_id)
        if not submission:
            await interaction.followup.send(
                "❌ Submission not found.",
                ephemeral=True
            )
            return

        await db_service.approve_submission(
            submission_id=self.submission_id,
            approved_by=str(interaction.user.id)
        )

        # Update original message
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
                embed.add_field(
                    name="Approved At",
                    value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>",
                    inline=True
                )
                await message.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Failed to update submission message: {e}")

        await db_service.log_action(
            action_type="SUBMISSION_APPROVED",
            performed_by=str(interaction.user.id),
            target_user=submission.discord_id,
            details={"submission_id": self.submission_id}
        )

        await interaction.followup.send(
            f"✅ Submission #{self.submission_id} approved.",
            ephemeral=True
        )

    # ❌ REJECT BUTTON
    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.red,
        custom_id="reject_submission"
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        modal = RejectSubmissionModal(self.submission_id)
        await interaction.response.send_modal(modal)


# =========================
# 📦 Interaction Cog
# =========================
class InteractionHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 🔨 Register persistent views on startup
    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ InteractionHandlers loaded")

    # 🛑 Ban profile button (used elsewhere)
    async def show_ban_profile_modal(
        self,
        interaction: discord.Interaction,
        profile_id: int
    ):
        modal = BanProfileModal(profile_id)
        await interaction.response.send_modal(modal)


# =========================
# 🚀 Setup
# =========================
async def setup(bot: commands.Bot):
    await bot.add_cog(InteractionHandlers(bot))
