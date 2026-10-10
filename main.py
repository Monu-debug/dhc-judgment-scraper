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
# Default listing URL for Delhi High Court judgments
DEFAULT_LISTING_URL = "https://delhihighcourt.nic.in/web/judgement/fetch-data"
# Time window for running (IST)
RUN_START_TIME = time(16, 0)   # 4:00 PM
RUN_END_TIME = time(16, 5)     # 4:05 PM
# Timezone offset for IST (UTC+5:30)
IST_OFFSET = timedelta(hours=5, minutes=30)

# Default filtering keywords (can be extended via environment variables)
DEFAULT_INCOME_TAX_KEYWORDS = [
    "income tax",
    "income-tax",
    "commissioner of income tax",
    "commissioner of income-tax",
    "assessing officer",
    "income tax officer",
    "acit",
    "dcit",
    "pcit",
    "cit",
    "ccit",
    "pccit",
    "ao",
    "ito",
    "itat",
    "cbdt",
    "dgit",
    "ita",
    "itr"
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
    "interim order",
    "interim stay",
    "interim relief",
    "ad interim",
    "adjournment",
    "adjourned",
    "stay application",
    "interlocutory application",
    "matter adjourned"
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

def run_scraper(force: bool = False, sync_only: bool = False) -> dict:
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

    # Determine max days old for date filtering
    max_days_env = os.getenv('MAX_DAYS_OLD')
    if max_days_env is not None and max_days_env.strip() != "":
        max_days_old = int(max_days_env) if max_days_env.isdigit() else None
    else:
        # Default: 3 days on Sat-Mon to cover Friday's orders, 2 days on Tue-Fri
        now_utc = datetime.utcnow()
        now_ist = now_utc + IST_OFFSET
        max_days_old = 3 if now_ist.weekday() in (0, 5, 6) else 2

    # Combine default and additional keywords
    income_tax_keywords = DEFAULT_INCOME_TAX_KEYWORDS + additional_income_tax_keywords
    final_judgment_keywords = DEFAULT_FINAL_JUDGMENT_KEYWORDS + additional_final_keywords
    exclude_keywords = DEFAULT_EXCLUDE_KEYWORDS

    logger.info(f"Using {len(income_tax_keywords)} income tax keywords")
    logger.info(f"Using {len(final_judgment_keywords)} final judgment keywords")
    logger.info(f"Using {len(exclude_keywords)} exclusion keywords")
    logger.info(f"Max judgment age filter: {max_days_old} days" if max_days_old else "Age filter disabled")

    # Load sent judgments
    sent_count_before = storage.get_sent_count()
    logger.info(f"Loaded {sent_count_before} previously sent judgment IDs from storage")

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

    # Filter for income tax final judgments (with date age cutoff)
    filtered_judgments = scraper.filter_judgments(
        judgments,
        income_tax_keywords,
        final_judgment_keywords,
        exclude_keywords,
        max_days_old=max_days_old
    )
    logger.info(f"Filtered to {len(filtered_judgments)} income tax final judgments")

    # Filter out already sent judgments
    new_judgments = []
    for judgment in filtered_judgments:
        judgment_id = scraper.generate_judgment_id(judgment)
        if not storage.is_judgment_sent(judgment_id):
            new_judgments.append((judgment, judgment_id))

    logger.info(f"Found {len(new_judgments)} new judgments to process")

    # If in sync_only mode, mark all current judgments as seen without sending
    if sync_only or os.getenv('SYNC_ONLY', '').lower() in ('1', 'true', 'yes') or '--sync-only' in sys.argv:
        new_ids = [j_id for _, j_id in new_judgments]
        storage.mark_all_seen(new_ids)
        logger.info(f"Marked {len(new_ids)} current judgments as seen without sending notifications.")
        return {
            "status": "success",
            "message": f"Marked {len(new_ids)} judgments as seen. Future runs will only notify about new ones.",
            "synced_count": len(new_ids),
            "total_seen": storage.get_sent_count()
        }

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
    sync_only = '--sync-only' in sys.argv
    result = run_scraper(force=force, sync_only=sync_only)
    return 0 if result.get("status") in ("success", "skipped") else 1

if __name__ == "__main__":
    sys.exit(main())