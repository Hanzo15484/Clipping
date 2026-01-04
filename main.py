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
        self.view_tracker = None
        
    async def setup_hook(self):
        """Setup the bot after login"""
        try:
            # Initialize database
            await self.db_service.initialize()
            
            # Load cogs
            await self.load_cogs()
            
            # Sync commands
            await self.sync_commands()
            
            # Initialize view tracker
            self.view_tracker = ViewTracker(self)
            
            # Start background tasks
            if self.view_tracker:
                self.view_tracker.start_tracking()
            
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error in setup_hook: {e}")
            raise
            
    async def load_cogs(self):
        """Load all cogs"""
        cogs = [
            "commands.user_commands",
            "commands.staff_commands",
            "commands.admin_commands",
            "commands.campaign_commands",
            "commands.payment_commands",
            "events.interaction_handlers"
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
                # Don't raise, just log
                
    async def sync_commands(self):
        """Sync slash commands"""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Set up channels
        await self.setup_channels()
        
        try:
            await self.db_service.log_action(
                action_type='BOT_STARTED',
                performed_by='system',
                details={'status': 'online', 'guilds': len(self.guilds)}
            )
        except Exception as e:
            logger.error(f"Error logging bot start: {e}")
        
    async def setup_channels(self):
        """Set up required channels"""
        try:
            log_channel_id = int(os.getenv('LOG_CHANNEL_ID', '0'))
            submission_channel_id = int(os.getenv('SUBMISSION_CHANNEL_ID', '0'))
            
            if log_channel_id:
                self.log_channel = self.get_channel(log_channel_id)
                if self.log_channel:
                    logger.info(f"Log channel set: {self.log_channel.name}")
                else:
                    logger.warning(f"Log channel ID {log_channel_id} not found")
                    
            if submission_channel_id:
                self.submission_channel = self.get_channel(submission_channel_id)
                if self.submission_channel:
                    logger.info(f"Submission channel set: {self.submission_channel.name}")
                else:
                    logger.warning(f"Submission channel ID {submission_channel_id} not found")
                    
        except Exception as e:
            logger.error(f"Error setting up channels: {e}")
                
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down...")
        if self.view_tracker:
            self.view_tracker.stop_tracking()
        await self.db_service.close()
        await super().close()

async def main():
    """Main entry point"""
    bot = CLBot()
    
    try:
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN not found in environment variables")
            print("❌ ERROR: Please set DISCORD_TOKEN in .env file")
            return
            
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await bot.close()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        await bot.close()

if __name__ == "__main__":
    print("🚀 Starting CL Bot...")
    asyncio.run(main())

