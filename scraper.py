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
        urls_to_try = [listing_url]
        fallbacks = [
            "https://delhihighcourt.nic.in/web/judgement/fetch-data",
            "https://delhihighcourt.nic.in"
        ]
        for fb in fallbacks:
            if fb not in urls_to_try:
                urls_to_try.append(fb)

        for target_url in urls_to_try:
            try:
                logger.info(f"Fetching judgments from: {target_url}")
                response = self.session.get(target_url, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"HTTP {response.status_code} from {target_url}, trying next fallback...")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                judgments = []

                # Strategy 1: Check table rows (used by /web/judgement/fetch-data)
                rows = soup.select('table tr')
                for row in rows:
                    judgment = self._parse_judgment_element(row)
                    if judgment:
                        judgments.append(judgment)

                # Strategy 2: Check ticker & announcement list items (used by homepage)
                if not judgments:
                    ticker_items = soup.select('.latest-announc-ticker li, .latest-announc-area li, ul.announcements li, li')
                    for item in ticker_items:
                        judgment = self._parse_judgment_element(item)
                        if judgment:
                            judgments.append(judgment)

                # Strategy 3: Fallback to any PDF links
                if not judgments:
                    links = soup.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if 'showfilejudgment' in href.lower() or href.lower().endswith('.pdf'):
                            judgment = self._parse_judgment_element(link)
                            if judgment:
                                judgments.append(judgment)

                if judgments:
                    logger.info(f"Successfully extracted {len(judgments)} judgment candidates from {target_url}")
                    return judgments
                else:
                    logger.warning(f"No judgments found on {target_url}, trying next fallback...")

            except Exception as e:
                logger.error(f"Error fetching judgments listing from {target_url}: {e}")

        return []

    def _parse_judgment_element(self, element) -> Optional[Dict]:
        """
        Parse an HTML element (table row or list item) to extract judgment details.
        Returns a dictionary with judgment information or None if not a judgment.
        """
        try:
            # Check if this is a table row (tr) with standard Delhi High Court columns
            tds = element.find_all('td')
            if len(tds) >= 5:
                # Column 1: Case No, Column 2: Judgment Date, Column 3: Petitioner, Column 4: Respondent, Column 5: Download
                case_number = tds[1].get_text(strip=True)
                date = tds[2].get_text(strip=True)
                petitioner = tds[3].get_text(strip=True)
                respondent = tds[4].get_text(strip=True)
                title = f"{petitioner} Vs {respondent}" if petitioner and respondent else case_number

                download_link = tds[5].find('a', href=True) if len(tds) > 5 else element.find('a', href=True)
                pdf_url = urljoin(self.base_url, download_link['href']) if download_link else None

                raw_text = f"{case_number} {title} {petitioner} {respondent} {date} judgment order"
                return {
                    'title': title,
                    'date': date,
                    'case_number': case_number,
                    'pdf_url': pdf_url,
                    'raw_text': raw_text,
                    'element_html': str(element)[:500]
                }

            # General element (li, div, a)
            text = element.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:
                return None

            links = element.find_all('a', href=True) if hasattr(element, 'find_all') else []
            if element.name == 'a' and element.get('href'):
                links = [element]

            pdf_url = None
            for link in links:
                href = link.get('href', '')
                if href.lower().endswith('.pdf') or 'showfilejudgment' in href.lower() or 'judgment' in href.lower() or 'order' in href.lower():
                    pdf_url = urljoin(self.base_url, href)
                    break

            if not pdf_url and links:
                pdf_url = urljoin(self.base_url, links[0]['href'])

            # Date extraction regex
            date_patterns = [
                r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}',
                r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'
            ]
            date = None
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date = match.group(0)
                    break

            # Case number extraction regex
            case_number_patterns = [
                r'[A-Za-z\.\(\)]+\s*-\s*\d+/\d{4}',
                r'[A-Za-z\.\(\)\s]+\d+/\d{4}',
                r'\d+/\d{4}'
            ]
            case_number = None
            for pattern in case_number_patterns:
                match = re.search(pattern, text)
                if match:
                    case_number = match.group(0).strip()
                    break

            title = text[:250]
            raw_text = f"{title} judgment order"

            return {
                'title': title,
                'date': date,
                'case_number': case_number,
                'pdf_url': pdf_url,
                'raw_text': raw_text,
                'element_html': str(element)[:500]
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