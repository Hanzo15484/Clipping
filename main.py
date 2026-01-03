import os
import asyncio
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands

from database import Database
from services.database_service import DatabaseService
from services.view_tracker import ViewTracker
from utils.loggers import setup_logging

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging()

class CLBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db_service = DatabaseService()
        self.view_tracker = ViewTracker(self)
        
    async def setup_hook(self):
        """Setup the bot after login"""
        # Initialize database
        await self.db_service.initialize()
        
        # Load cogs
        await self.load_cogs()
        
        # Sync commands
        await self.sync_commands()
        
        # Start background tasks
        self.view_tracker.start_tracking()
        
    async def load_cogs(self):
        """Load all cogs"""
        # Load command cogs
        await self.load_extension("commands.user_commands")
        await self.load_extension("commands.staff_commands")
        await self.load_extension("commands.admin_commands")
        await self.load_extension("commands.campaign_commands")
        await self.load_extension("commands.payment_commands")
        
        # Load event cogs
        await self.load_extension("events.interaction_handlers")
        await self.load_extension("events.modal_handlers")
        
        logger.info("All cogs loaded successfully")
        
    async def sync_commands(self):
        """Sync slash commands"""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Logged in as {self.user}")
        
        # Set up channels
        await self.setup_channels()
        
        await self.db_service.log_action(
            action_type='BOT_STARTED',
            performed_by='system',
            details={'status': 'online'}
        )
        
    async def setup_channels(self):
        """Set up required channels"""
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', '0'))
        submission_channel_id = int(os.getenv('SUBMISSION_CHANNEL_ID', '0'))
        
        if log_channel_id:
            self.log_channel = self.get_channel(log_channel_id)
            if self.log_channel:
                logger.info(f"Log channel set: {self.log_channel.name}")
                
        if submission_channel_id:
            self.submission_channel = self.get_channel(submission_channel_id)
            if self.submission_channel:
                logger.info(f"Submission channel set: {self.submission_channel.name}")
                
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down...")
        self.view_tracker.stop_tracking()
        await self.db_service.close()
        await super().close()

async def main():
    """Main entry point"""
    bot = CLBot()
    
    try:
        await bot.start(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
