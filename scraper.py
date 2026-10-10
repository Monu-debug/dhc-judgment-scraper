import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

class DelhiHighCourtScraper:
    def __init__(self, base_url: str = "https://delhihighcourt.nic.in"):
        self.base_url = base_url
        self.session = requests.Session()
        # Set a user-agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def fetch_judgments_listing(self, listing_url: str) -> List[Dict]:
        """
        Fetch the judgments listing page and extract judgment entries.
        Returns a list of dictionaries with keys: title, date, case_number, pdf_url, raw_text
        """
        try:
            logger.info(f"Fetching judgments from: {listing_url}")
            response = self.session.get(listing_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Try to find judgment entries - adjust these selectors based on actual site structure
            # Common patterns for judgment listings on court websites
            selectors = [
                'tr',  # Table rows
                '.judgment-item',
                '.cause-list-item',
                '.judgment-row',
                '.case-item',
                'li',  # List items
                '.entry'
            ]

            judgment_elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"Found {len(elements)} elements using selector: {selector}")
                    judgment_elements = elements
                    break

            if not judgment_elements:
                logger.warning("Could not find judgment elements with common selectors")
                # Fallback: look for any links that might be judgments
                judgment_elements = soup.find_all('a', href=True)

            judgments = []
            for element in judgment_elements:
                judgment = self._parse_judgment_element(element)
                if judgment:
                    judgments.append(judgment)

            logger.info(f"Extracted {len(judgments)} judgment candidates")
            return judgments

        except Exception as e:
            logger.error(f"Error fetching judgments listing: {e}")
            return []

    def _parse_judgment_element(self, element) -> Optional[Dict]:
        """
        Parse a single HTML element to extract judgment details.
        Returns a dictionary with judgment information or None if not a judgment.
        """
        try:
            # Extract text content
            text = element.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:  # Too short to be a judgment
                return None

            # Extract links
            links = element.find_all('a', href=True)
            pdf_url = None
            for link in links:
                href = link['href']
                # Look for PDF links or judgment links
                if href.lower().endswith('.pdf') or 'judgment' in href.lower() or 'order' in href.lower():
                    pdf_url = urljoin(self.base_url, href)
                    break

            # If no specific judgment link, take the first link
            if not pdf_url and links:
                pdf_url = urljoin(self.base_url, links[0]['href'])

            # Try to extract date using regex
            date_patterns = [
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or MM/DD/YYYY
                r'\d{2,4}[/-]\d{1,2}[/-]\d{1,2}',  # YYYY/MM/DD
                r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'
            ]
            date = None
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date = match.group(0)
                    break

            # Try to extract case number (common patterns: WP(C) 123/2023, CS(OS) 456/2023)
            case_number_patterns = [
                r'[A-Za-z]+\s*\d+/\d{4}',  # e.g., WP(C) 123/2023
                r'\d+/\d{4}',               # e.g., 123/2023
                r'[A-Za-z]+\(\s*[A-Za-z]+\s*\)\s*\d+/\d{4}'  # e.g., WP(C) 123/2023
            ]
            case_number = None
            for pattern in case_number_patterns:
                match = re.search(pattern, text)
                if match:
                    case_number = match.group(0).strip()
                    break

            # If we couldn't extract structured data, use the whole text as title
            title = text[:200]  # Limit title length

            return {
                'title': title,
                'date': date,
                'case_number': case_number,
                'pdf_url': pdf_url,
                'raw_text': text,
                'element_html': str(element)[:500]  # For debugging
            }

        except Exception as e:
            logger.debug(f"Error parsing judgment element: {e}")
            return None

    def filter_judgments(self, judgments: List[Dict],
                        income_tax_keywords: List[str],
                        final_judgment_keywords: List[str],
                        exclude_keywords: List[str]) -> List[Dict]:
        """
        Filter judgments for final income tax judgments.
        Returns a list of judgments that match the criteria.
        """
        filtered = []

        for judgment in judgments:
            # Combine text fields for searching
            search_text = f"{judgment['title']} {judgment.get('case_number', '')} {judgment.get('date', '')} {judgment.get('raw_text', '')}".lower()

            # Check for income tax keywords
            income_tax_match = any(keyword.lower() in search_text for keyword in income_tax_keywords)
            if not income_tax_match:
                continue

            # Check for final judgment keywords
            final_judgment_match = any(keyword.lower() in search_text for keyword in final_judgment_keywords)
            if not final_judgment_match:
                continue

            # Check for exclusion keywords (interim/procedural)
            exclude_match = any(keyword.lower() in search_text for keyword in exclude_keywords)
            if exclude_match:
                continue

            filtered.append(judgment)

        return filtered

    def generate_judgment_id(self, judgment: Dict) -> str:
        """
        Generate a unique identifier for a judgment.
        Uses case number and date if available, otherwise falls back to a hash of the title.
        """
        case_number = judgment.get('case_number', '')
        date = judgment.get('date', '')

        if case_number and date:
            # Create a clean ID: remove special characters and spaces
            clean_case = re.sub(r'[^\w\-]', '', case_number)
            clean_date = re.sub(r'[^\w\-]', '', date)
            return f"{clean_case}_{clean_date}"
        else:
            # Fallback to hash of title
            return str(hash(judgment.get('title', '')))