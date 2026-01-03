import logging
import json
import os
from typing import Optional, Dict, Any
import discord

def setup_logging() -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class DiscordLogger:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = int(os.getenv('LOG_CHANNEL_ID', '0'))
        
    async def log_to_discord(self, action_type: str, performed_by: str, 
                           target_user: Optional[str] = None, details: Dict[str, Any] = None):
        """Log action to Discord channel"""
        if not self.log_channel_id:
            return
            
        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            return
            
        embed = discord.Embed(
            title=f"📝 {action_type}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        if performed_by != 'system':
            embed.description = f"Action performed by <@{performed_by}>"
            
        if details:
            embed.add_field(
                name="Details",
                value=f"```json\n{json.dumps(details, indent=2)}\n```",
                inline=False
            )
            
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Failed to send log to Discord: {e}")
