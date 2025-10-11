"""
Telegram notification utilities for NBA Grid API.

This module provides functionality to send notifications to Telegram
about NBA data update operations and other important events.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from django.conf import settings
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending notifications to Telegram."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize the Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (defaults to settings.TELEGRAM_BOT_TOKEN)
            chat_id: Telegram chat ID (defaults to settings.TELEGRAM_CHAT_ID)
        """
        self.bot_token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = chat_id or getattr(settings, 'TELEGRAM_CHAT_ID', None)
        self.bot = None
        
        if self.bot_token:
            self.bot = Bot(token=self.bot_token)
    
    def is_configured(self) -> bool:
        """Check if Telegram notifications are properly configured."""
        return bool(self.bot_token and self.chat_id)
    
    async def send_message_async(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message to Telegram asynchronously.
        
        Args:
            message: The message to send
            parse_mode: Telegram parse mode ('HTML' or 'Markdown')
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("Telegram notifications not configured - skipping message")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Telegram notification sent successfully")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message to Telegram synchronously.
        
        Args:
            message: The message to send
            parse_mode: Telegram parse mode ('HTML' or 'Markdown')
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("Telegram notifications not configured - skipping message")
            return False
        
        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.send_message_async(message, parse_mode))
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error running async Telegram notification: {e}")
            return False


class NBADataUpdateSummary:
    """Generates summaries for NBA data update operations."""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.operations: Dict[str, Dict[str, Any]] = {}
        self.errors: list = []
        self.total_success_count = 0
        self.total_error_count = 0
    
    def set_start_time(self, start_time: datetime):
        """Set the operation start time."""
        self.start_time = start_time
    
    def set_end_time(self, end_time: datetime):
        """Set the operation end time."""
        self.end_time = end_time
    
    def add_operation(self, operation_name: str, success_count: int = 0, 
                     error_count: int = 0, details: Optional[str] = None):
        """
        Add an operation result to the summary.
        
        Args:
            operation_name: Name of the operation (e.g., 'players', 'teams', 'stats')
            success_count: Number of successful operations
            error_count: Number of failed operations
            details: Additional details about the operation
        """
        self.operations[operation_name] = {
            'success_count': success_count,
            'error_count': error_count,
            'details': details
        }
        self.total_success_count += success_count
        self.total_error_count += error_count
    
    def add_error(self, error_message: str):
        """Add an error message to the summary."""
        self.errors.append(error_message)
        self.total_error_count += 1
    
    def get_duration(self) -> Optional[timedelta]:
        """Get the total operation duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def generate_telegram_message(self) -> str:
        """
        Generate a formatted Telegram message for the NBA data update summary.
        
        Returns:
            Formatted HTML message for Telegram
        """
        # Header with emoji based on success/failure
        if self.total_error_count == 0:
            status_emoji = "✅"
            status_text = "SUCCESS"
        elif self.total_success_count > 0:
            status_emoji = "⚠️"
            status_text = "PARTIAL SUCCESS"
        else:
            status_emoji = "❌"
            status_text = "FAILED"
        
        message_parts = [
            f"{status_emoji} <b>NBA Data Update {status_text}</b>",
            ""
        ]
        
        # Duration
        duration = self.get_duration()
        if duration:
            duration_str = f"{duration.total_seconds():.1f}s"
            message_parts.append(f"⏱️ <b>Duration:</b> {duration_str}")
        
        # Overall stats
        message_parts.extend([
            f"📊 <b>Total Operations:</b> {self.total_success_count + self.total_error_count}",
            f"✅ <b>Successful:</b> {self.total_success_count}",
            f"❌ <b>Failed:</b> {self.total_error_count}",
            ""
        ])
        
        # Operation details
        if self.operations:
            message_parts.append("📋 <b>Operations:</b>")
            for op_name, op_data in self.operations.items():
                success = op_data['success_count']
                errors = op_data['error_count']
                
                if errors == 0:
                    op_emoji = "✅"
                elif success > 0:
                    op_emoji = "⚠️"
                else:
                    op_emoji = "❌"
                
                op_line = f"{op_emoji} <i>{op_name.title()}:</i> {success} ok"
                if errors > 0:
                    op_line += f", {errors} failed"
                
                message_parts.append(op_line)
            
            message_parts.append("")
        
        # Error details (limit to first 3 errors to avoid message length limits)
        if self.errors:
            message_parts.append("🚨 <b>Errors:</b>")
            for error in self.errors[:3]:
                # Truncate long error messages
                if len(error) > 100:
                    error = error[:97] + "..."
                message_parts.append(f"• <code>{error}</code>")
            
            if len(self.errors) > 3:
                message_parts.append(f"... and {len(self.errors) - 3} more errors")
            
            message_parts.append("")
        
        # Footer
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        message_parts.extend([
            f"🕐 <i>Completed at {timestamp}</i>",
            f"🏀 <i>NBA Grid API Data Updater</i>"
        ])
        
        return "\n".join(message_parts)


def send_nba_update_notification(summary: NBADataUpdateSummary) -> bool:
    """
    Send an NBA data update notification to Telegram.
    
    Args:
        summary: The update summary to send
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    notifier = TelegramNotifier()
    
    if not notifier.is_configured():
        logger.info("Telegram notifications not configured - skipping notification")
        return False
    
    message = summary.generate_telegram_message()
    return notifier.send_message(message)
