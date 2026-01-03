import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PermissionManager
from services.database_service import DatabaseService

db_service = DatabaseService()

class PaymentCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service
        
    @app_commands.command(name="wallet", description="[Staff] View user wallet info")
    @app_commands.describe(user="User to check")
    async def wallet(self, interaction: discord.Interaction, user: discord.User):
        """View user wallet information"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_data = await self.db_service.get_user(str(user.id))
            if not user_data:
                await interaction.followup.send(
                    "❌ User not found.",
                    ephemeral=True
                )
                return
                
            # Get pending payouts
            pending_payouts = await self.db_service.get_pending_payouts(str(user.id))
            
            # Get user stats
            stats = await self.db_service.get_user_stats(str(user.id))
            
            embed = discord.Embed(
                title="💰 Wallet Information",
                description=f"User: <@{user.id}>",
                color=discord.Color.purple(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="Total Earnings",
                value=f"${user_data.total_earnings:.2f}",
                inline=True
            )
            embed.add_field(
                name="Paid",
                value=f"${user_data.paid_earnings:.2f}",
                inline=True
            )
            embed.add_field(
                name="Pending",
                value=f"${user_data.pending_earnings:.2f}",
                inline=True
            )
            embed.add_field(
                name="USDT Wallet",
                value=f"`{user_data.usdt_wallet}`" if user_data.usdt_wallet else "Not set",
                inline=False
            )
            
            if stats.get('total_submissions', 0) > 0:
                embed.add_field(
                    name="📊 Stats",
                    value=f"Submissions: {stats['total_submissions']}\nTotal Views: {stats.get('total_views', 0):,}\nTotal Earned: ${stats.get('total_earned', 0):.2f}",
                    inline=False
                )
                
            if pending_payouts:
                payout_text = "\n".join([
                    f"**{payout['campaign_name']}:** ${payout['amount']:.2f}"
                    for payout in pending_payouts
                ])
                embed.add_field(name="Pending Payouts", value=payout_text)
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while fetching wallet info.",
                ephemeral=True
            )
            raise
            
    @app_commands.command(name="payout-mark-paid", description="[Staff] Mark payout as paid")
    @app_commands.describe(
        user="User",
        campaign="Campaign name",
        amount="Amount in USD",
        tx_hash="USDT transaction hash"
    )
    async def payout_mark_paid(self, interaction: discord.Interaction,
                              user: discord.User, campaign: str,
                              amount: float, tx_hash: str):
        """Mark a payout as paid"""
        if not await PermissionManager.enforce_permission(interaction, 'staff'):
            return
            
        try:
            # Get campaign
            campaign_data = await self.db_service.get_campaign_by_name(campaign)
            if not campaign_data:
                await interaction.response.send_message(
                    "❌ Campaign not found.",
                    ephemeral=True
                )
                return
                
            # Create payout record
            await self.db_service.create_payout(
                discord_id=str(user.id),
                campaign_id=campaign_data.id,
                amount=amount,
                usdt_tx_hash=tx_hash,
                paid_by=str(interaction.user.id)
            )
            
            await interaction.response.send_message(
                f"✅ Payout marked as paid for <@{user.id}>. TX: `{tx_hash}`",
                ephemeral=True
            )
            
            await self.db_service.log_action(
                action_type='PAYOUT_MARKED_PAID',
                performed_by=str(interaction.user.id),
                target_user=str(user.id),
                details={
                    'campaign': campaign,
                    'amount': amount,
                    'tx_hash': tx_hash
                }
            )
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ An error occurred while marking payout as paid.",
                ephemeral=True
            )
            raise

async def setup(bot):
    await bot.add_cog(PaymentCommands(bot))
