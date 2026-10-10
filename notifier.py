import logging
from typing import List, Dict
import requests
import os

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize the Telegram notifier using Telegram Bot HTTP API.
        If bot_token or chat_id are not provided, they will be read from environment variables:
        - TELEGRAM_BOT_TOKEN
        - TELEGRAM_CHAT_ID
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.is_configured = False

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not fully set. Notifications will be logged but not sent.")
        else:
            try:
                # Test connection via getMe
                res = requests.get(f"https://api.telegram.org/bot{self.bot_token}/getMe", timeout=10)
                if res.status_code == 200 and res.json().get('ok'):
                    bot_name = res.json().get('result', {}).get('username', 'Bot')
                    logger.info(f"Telegram bot initialized successfully (@{bot_name})")
                    self.is_configured = True
                else:
                    logger.error(f"Failed to initialize Telegram bot: {res.text}")
            except Exception as e:
                logger.error(f"Failed to connect to Telegram API: {e}")

    def send_judgment_notification(self, judgment: Dict) -> bool:
        """
        Send a single judgment notification via Telegram.
        Returns True if successful, False otherwise.
        """
        if not self.is_configured:
            logger.debug(f"Telegram bot not configured. Would send: {self._format_judgment_message(judgment)}")
            return False

        try:
            message = self._format_judgment_message(judgment)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200 and res.json().get('ok'):
                logger.info(f"Sent Telegram notification for judgment: {judgment.get('case_number', 'Unknown')}")
                return True
            else:
                logger.error(f"Telegram API error: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False

    def send_judgments_notification(self, judgments: List[Dict]) -> int:
        """
        Send notifications for multiple judgments.
        Returns the number of successfully sent notifications.
        """
        if not judgments:
            logger.info("No judgments to send")
            return 0

        sent_count = 0
        for judgment in judgments:
            if self.send_judgment_notification(judgment):
                sent_count += 1
            # Add a small delay to avoid hitting rate limits
            # import time
            # time.sleep(0.1)

        logger.info(f"Sent {sent_count} out of {len(judgments)} judgments via Telegram")
        return sent_count

    def _format_judgment_message(self, judgment: Dict) -> str:
        """
        Format a judgment into a Telegram message using HTML for formatting.
        """
        # Escape HTML entities in the judgment data to prevent breaking the message
        def escape_html(text):
            if not text:
                return ""
            return (text.replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace('"', "&quot;")
                       .replace("'", "&#x27;"))

        case_number = escape_html(judgment.get('case_number', 'N/A'))
        date = escape_html(judgment.get('date', 'N/A'))
        title = escape_html(judgment.get('title', 'N/A'))
        pdf_url = judgment.get('pdf_url', '')

        message = f"<b>New Income Tax Judgment - Delhi High Court</b>\n\n"
        message += f"<b>Case Number:</b> {case_number}\n"
        message += f"<b>Date:</b> {date}\n"
        message += f"<b>Subject:</b> {title}\n"

        if pdf_url:
            # Make the link clickable
            message += f"<b>PDF Link:</b> <a href=\"{pdf_url}\">Download Judgment PDF</a>\n"
        else:
            message += f"<b>PDF Link:</b> Not available\n"

        message += f"<b>Source:</b> Delhi High Court Website"

        return message

    def send_test_message(self) -> bool:
        """Send a test message to verify the bot is working"""
        if not self.is_configured:
            logger.warning("Telegram bot not configured for test message")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": "<b>Test message from Delhi High Court Judgment Scraper</b>\n\nIf you see this, the bot is configured correctly!",
                "parse_mode": "HTML"
            }
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200 and res.json().get('ok'):
                logger.info("Test message sent successfully")
                return True
            else:
                logger.error(f"Failed to send test message: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            return False