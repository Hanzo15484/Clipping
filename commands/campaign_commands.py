import discord
from discord import app_commands
from discord.ext import commands

from services.database_service import DatabaseService
from services.campaign_service import CampaignService

db_service = DatabaseService()
campaign_service = CampaignService()

class CampaignCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_service = db_service
        self.campaign_service = campaign_service
        
    @app_commands.command(name="campaign-list", description="List all campaigns")
    async def campaign_list(self, interaction: discord.Interaction):
        """List all campaigns"""
        await interaction.response.defer()
        
        try:
            campaigns = await self.campaign_service.get_all_campaigns()
            
            if not campaigns:
                await interaction.followup.send("No campaigns found.")
                return
                
            embed = discord.Embed(
                title="📊 Campaign List",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            for campaign in campaigns:
                status_emoji = "🟢" if campaign.status == 'live' else "🔴"
                value = f"""
                    **Platform:** {campaign.platform}
                    **Budget:** ${campaign.remaining_budget:.2f} / ${campaign.total_budget:.2f}
                    **Rate:** ${campaign.rate_per_100k}/100K | ${campaign.rate_per_1m}/1M
                    **Min Views:** {campaign.min_views:,}
                    **Status:** {status_emoji} {campaign.status}
                """
                embed.add_field(
                    name=f"{campaign.name}",
                    value=value,
                    inline=False
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ An error occurred while fetching campaigns."
            )

async def setup(bot):
    await bot.add_cog(CampaignCommands(bot))
