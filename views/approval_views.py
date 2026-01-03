import discord
from views.modal_views import RejectProfileModal

class ProfileReviewView(discord.ui.View):
    def __init__(self, profile_id: int):
        super().__init__(timeout=None)
        self.profile_id = profile_id
        
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="approve_profile")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from services.database_service import DatabaseService
        db_service = DatabaseService()
        
        try:
            await db_service.approve_profile(self.profile_id, str(interaction.user.id))
            
            await interaction.response.send_message(
                f"✅ Profile #{self.profile_id} approved.",
                ephemeral=True
            )
            
            await db_service.log_action(
                action_type='PROFILE_APPROVED',
                performed_by=str(interaction.user.id),
                details={'profile_id': self.profile_id}
            )
            
        except Exception as e:
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
