#!/usr/bin/env python3
"""
Main script for Delhi High Court Income Tax Judgment Scraper and Notifier.
Orchestrates scraping, filtering, storage, and notification.
Runs daily at 4:00 PM IST (within a 5-minute window) using the loop skill.
"""
import logging
import os
from datetime import datetime, timedelta, time
from typing import List
import sys

# Import local modules
from scraper import DelhiHighCourtScraper
from storage import JudgmentStorage
from notifier import TelegramNotifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("judgment_scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
# Default listing URL for Delhi High Court judgments - user may need to adjust
DEFAULT_LISTING_URL = "https://delhihighcourt.nic.in/app/getjudgments"
# Time window for running (IST)
RUN_START_TIME = time(16, 0)   # 4:00 PM
RUN_END_TIME = time(16, 5)     # 4:05 PM
# Timezone offset for IST (UTC+5:30)
IST_OFFSET = timedelta(hours=5, minutes=30)

# Default filtering keywords (can be extended via environment variables)
DEFAULT_INCOME_TAX_KEYWORDS = [
    "income tax",
    "ittat",
    "direct tax",
    "revenue",
    "tax",
    "assessment",
    "section",
    "appellate",
    "tribunal",
    "commissioner",
    "addl.",
    "joint",
    "deputy",
    "assistant",
    "cit",
    "cbd t",
    "capital gains",
    "salary",
    "house property",
    "business",
    "other sources"
]

DEFAULT_FINAL_JUDGMENT_KEYWORDS = [
    "final judgment",
    "final order",
    "judgment",
    "order",
    "disposed of",
    "dismissed",
    "allowed",
    "affirmed",
    "reversed",
    "remanded",
    "held",
    "declared",
    "directed",
    "ordered",
    "struck down",
    "upheld",
    "valid",
    "invalid",
    "constitutional",
    "unconstitutional"
]

DEFAULT_EXCLUDE_KEYWORDS = [
    "interim",
    "interlocutory",
    "procedural",
    "admission",
    "notice",
    "stay",
    "adjournment",
    "directions",
    "mention",
    "listing",
    "for orders",
    "for hearing",
    "argument",
    "appearance",
    "charge",
    "framing",
    "notice",
    "rule",
    "notice of motion",
    "motion",
    "application",
    "petition",
    "reply",
    "rejoinder",
    "affidavit",
    "written arguments",
    "written submissions",
    "oral arguments",
    "oral submissions",
    "cross examination",
    "examination in chief",
    "re-examination",
    "evidence",
    "affidavit",
    "document",
    "exhibit",
    "marked",
    "not marked",
    "id",
    "proof",
    "prooft",
    "marked as",
    "marked as exhibit"
]

def is_within_time_window(force: bool = False) -> bool:
    """
    Check if the current time in IST is within the RUN_START_TIME and RUN_END_TIME window.
    Returns True if within window, False otherwise.
    Can be bypassed by setting FORCE_RUN=true, IGNORE_TIME_WINDOW=true, or passing --force.
    """
    if force or \
       os.getenv('FORCE_RUN', '').lower() in ('1', 'true', 'yes') or \
       os.getenv('IGNORE_TIME_WINDOW', '').lower() in ('1', 'true', 'yes') or \
       '--force' in sys.argv:
        logger.info("Time window check bypassed (force/ignore time window enabled)")
        return True

    # Get current UTC time
    now_utc = datetime.utcnow()
    # Convert to IST by adding IST_OFFSET
    now_ist = now_utc + IST_OFFSET
    # Extract the time component
    current_time = now_ist.time()

    logger.debug(f"Current UTC time: {now_utc}")
    logger.debug(f"Current IST time: {now_ist}")
    logger.debug(f"Checking if {current_time} is between {RUN_START_TIME} and {RUN_END_TIME}")

    return RUN_START_TIME <= current_time <= RUN_END_TIME

def get_listing_url() -> str:
    """
    Get the Delhi High Court judgments listing URL.
    First checks environment variable LISTING_URL, then uses default.
    """
    url = os.getenv('LISTING_URL', DEFAULT_LISTING_URL)
    logger.info(f"Using judgments listing URL: {url}")
    return url

def get_additional_keywords() -> List[str]:
    """
    Get additional keywords from environment variables.
    User can set ADDITIONAL_INCOME_TAX_KEYWORDS and ADDITIONAL_FINAL_JUDGMENT_KEYWORDS
    as comma-separated strings.
    """
    additional_income_tax = os.getenv('ADDITIONAL_INCOME_TAX_KEYWORDS', '')
    additional_final = os.getenv('ADDITIONAL_FINAL_JUDGMENT_KEYWORDS', '')

    income_tax_ext = [k.strip() for k in additional_income_tax.split(',') if k.strip()]
    final_ext = [k.strip() for k in additional_final.split(',') if k.strip()]

    if income_tax_ext:
        logger.info(f"Added {len(income_tax_ext)} additional income tax keywords")
    if final_ext:
        logger.info(f"Added {len(final_ext)} additional final judgment keywords")

    return income_tax_ext, final_ext

def run_scraper(force: bool = False) -> dict:
    """
    Execute the scraping and notification pipeline.
    Returns a dictionary summarizing execution results.
    """
    logger.info("Starting Delhi High Court Income Tax Judgment Scraper")

    # Check if we are within the time window
    if not is_within_time_window(force=force):
        now_utc = datetime.utcnow()
        now_ist = now_utc + IST_OFFSET
        msg = (f"Current IST time: {now_ist.time().strftime('%H:%M:%S')}. "
               f"Not within run window ({RUN_START_TIME} to {RUN_END_TIME}). Skipping.")
        logger.info(msg)
        return {
            "status": "skipped",
            "message": msg,
            "sent_count": 0
        }

    logger.info("Starting scraping process.")

    # Initialize components
    scraper = DelhiHighCourtScraper()
    storage = JudgmentStorage()
    notifier = TelegramNotifier()

    # Get configuration
    listing_url = get_listing_url()
    additional_income_tax_keywords, additional_final_keywords = get_additional_keywords()

    # Combine default and additional keywords
    income_tax_keywords = DEFAULT_INCOME_TAX_KEYWORDS + additional_income_tax_keywords
    final_judgment_keywords = DEFAULT_FINAL_JUDGMENT_KEYWORDS + additional_final_keywords
    exclude_keywords = DEFAULT_EXCLUDE_KEYWORDS

    logger.info(f"Using {len(income_tax_keywords)} income tax keywords")
    logger.info(f"Using {len(final_judgment_keywords)} final judgment keywords")
    logger.info(f"Using {len(exclude_keywords)} exclusion keywords")

    # Load sent judgments
    sent_count_before = storage.get_sent_count()
    logger.info(f"Loaded {sent_count_before} previously sent judgment IDs")

    # Fetch judgments from the website
    judgments = scraper.fetch_judgments_listing(listing_url)
    if not judgments:
        logger.warning("No judgments fetched from the website")
        return {
            "status": "success",
            "message": "No judgments fetched from the website",
            "fetched_count": 0,
            "sent_count": 0
        }

    logger.info(f"Fetched {len(judgments)} total judgments from website")

    # Filter for income tax final judgments
    filtered_judgments = scraper.filter_judgments(
        judgments,
        income_tax_keywords,
        final_judgment_keywords,
        exclude_keywords
    )
    logger.info(f"Filtered to {len(filtered_judgments)} income tax final judgments")

    # Filter out already sent judgments
    new_judgments = []
    for judgment in filtered_judgments:
        judgment_id = scraper.generate_judgment_id(judgment)
        if not storage.is_judgment_sent(judgment_id):
            new_judgments.append((judgment, judgment_id))

    logger.info(f"Found {len(new_judgments)} new judgments to process")

    # Send notifications and update storage
    sent_count = 0
    for judgment, judgment_id in new_judgments:
        try:
            if notifier.send_judgment_notification(judgment):
                storage.mark_judgment_sent(judgment_id)
                sent_count += 1
                logger.debug(f"Sent and marked judgment: {judgment_id}")
            else:
                logger.warning(f"Failed to send notification for judgment: {judgment_id}")
        except Exception as e:
            logger.error(f"Error processing judgment {judgment_id}: {e}")

    # Save storage
    storage._save_sent_judgments()
    sent_count_after = storage.get_sent_count()
    logger.info(f"Saved storage. Sent judgments count: {sent_count_before} -> {sent_count_after}")

    logger.info(f"Successfully processed {sent_count} new judgments")
    return {
        "status": "success",
        "fetched_count": len(judgments),
        "filtered_count": len(filtered_judgments),
        "new_count": len(new_judgments),
        "sent_count": sent_count
    }

def main():
    """Main execution function for CLI"""
    force = '--force' in sys.argv
    result = run_scraper(force=force)
    return 0 if result.get("status") in ("success", "skipped") else 1

if __name__ == "__main__":
    sys.exit(main())