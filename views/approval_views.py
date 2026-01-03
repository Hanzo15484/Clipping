import discord
import logging
from datetime import datetime, timezone, timedelta
from views.modal_views import RejectProfileModal
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)
db_service = DatabaseService()

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

class ProfileReviewView(discord.ui.View):
    def __init__(self, profile_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.profile_id = profile_id
        
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="approve_profile")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get profile
            profile = await db_service.get_profile_by_id(self.profile_id)
            
            if not profile:
                await interaction.response.send_message(
                    "❌ Profile not found.",
                    ephemeral=True
                )
                return
            
            # Approve profile
            await db_service.approve_profile(self.profile_id, str(interaction.user.id))
            
            # Update the original message
            embed = discord.Embed(
                title="✅ Profile Approved",
                description=f"Profile has been approved by <@{interaction.user.id}>",
                color=discord.Color.green(),
                timestamp=datetime.now(IST)
            )
            embed.add_field(name="User", value=f"<@{profile.discord_id}>", inline=True)
            embed.add_field(name="Platform", value=profile.platform, inline=True)
            embed.add_field(name="Profile URL", value=profile.profile_url, inline=False)
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Send confirmation
            await interaction.followup.send(
                f"✅ Profile #{self.profile_id} approved successfully.",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='PROFILE_APPROVED',
                performed_by=str(interaction.user.id),
                target_user=profile.discord_id,
                details={'profile_id': self.profile_id, 'profile_url': profile.profile_url}
            )
            
        except Exception as e:
            logger.error(f"Error approving profile: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while approving profile.",
                ephemeral=True
            )
            
    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="reject_profile")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RejectProfileModal(self.profile_id)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🚫 Ban", style=discord.ButtonStyle.secondary, custom_id="ban_profile_from_review")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from views.modal_views import BanProfileModal
        modal = BanProfileModal(self.profile_id)
        await interaction.response.send_modal(modal)
