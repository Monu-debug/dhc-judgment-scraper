import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime, timedelta

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

    @staticmethod
    def _parse_date_string(date_str: str):
        """Parse date string into a date object"""
        if not date_str:
            return None
        formats = [
            '%d %b %Y',
            '%d %B %Y',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%d.%m.%Y',
            '%Y-%m-%d'
        ]
        clean_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str.strip())
        for fmt in formats:
            try:
                return datetime.strptime(clean_str, fmt).date()
            except Exception:
                continue
        return None

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
                parsed_date = self._parse_date_string(date)
                return {
                    'title': title,
                    'petitioner': petitioner,
                    'respondent': respondent,
                    'date': date,
                    'parsed_date': parsed_date,
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
            parsed_date = self._parse_date_string(date)

            # Try to extract petitioner and respondent if "Vs" or "v." is in title
            parts = re.split(r'\s+(?:Vs|v\.|versus)\s+', title, flags=re.IGNORECASE)
            petitioner = parts[0].strip() if len(parts) > 1 else ""
            respondent = parts[1].strip() if len(parts) > 1 else ""

            return {
                'title': title,
                'petitioner': petitioner,
                'respondent': respondent,
                'date': date,
                'parsed_date': parsed_date,
                'case_number': case_number,
                'pdf_url': pdf_url,
                'raw_text': raw_text,
                'element_html': str(element)[:500]
            }

        except Exception as e:
            logger.debug(f"Error parsing judgment element: {e}")
            return None

    def is_income_tax_judgment(self, judgment: Dict, additional_keywords: List[str] = None) -> bool:
        """
        Filters judgment according to user specifications:
        1. Title/parties contains an Income Tax authority:
           ACIT, DCIT, PCIT, AO, ITO, CIT, CCIT, PCCIT, DGIT, DIT, ADIT, DDIT,
           Commissioner of Income Tax, Income Tax Officer, Assessing Officer, etc.
           or Case Type is ITA / ITR.
        2. OR either party is 'Union of India' (or UOI) AND mentions 'Income Tax'.
        """
        title = (judgment.get('title') or '').strip()
        petitioner = (judgment.get('petitioner') or '').strip()
        respondent = (judgment.get('respondent') or '').strip()
        case_number = (judgment.get('case_number') or '').strip()
        raw_text = (judgment.get('raw_text') or '').strip()

        # Focus party text on who is involved
        party_text = f"{title} {petitioner} {respondent}".lower()
        full_text = f"{party_text} {case_number} {raw_text}".lower()

        # Rule 1A: Specific authority phrases in party names
        authority_phrases = [
            "commissioner of income tax",
            "commissioner of income-tax",
            "income tax commissioner",
            "income-tax commissioner",
            "assessing officer",
            "income tax officer",
            "income-tax officer",
            "income tax department",
            "income-tax department",
            "income tax appellate tribunal",
            "central board of direct taxes",
            "director general of income tax",
            "principal commissioner of income tax",
            "chief commissioner of income tax",
            "pr. cit",
            "pr.cit"
        ]
        if any(phrase in party_text for phrase in authority_phrases):
            return True

        # Rule 1B: Authority acronyms with word boundaries in party names (e.g. ACIT, DCIT, PCIT, AO, ITO, CIT)
        authority_acronyms_pattern = (
            r'\b(acit|dcit|pcit|cit|ccit|pccit|p\.c\.i\.t\.|c\.i\.t\.|'
            r'ao|a\.o\.|ito|i\.t\.o\.|dgit|dit|adit|ddit|'
            r'itat|cbdt)\b'
        )
        if re.search(authority_acronyms_pattern, party_text, re.IGNORECASE):
            return True

        # Rule 1C: Direct Income Tax case type in case number (ITA = Income Tax Appeal, ITR = Income Tax Reference)
        if case_number and re.search(r'\b(ita|itr)\b', case_number, re.IGNORECASE):
            return True

        # Rule 2: "Union of India" (or UOI) present AND case explicitly mentions Income Tax
        has_uoi = bool(re.search(r'\b(union of india|uoi|u\.o\.i\.)\b', party_text, re.IGNORECASE))
        has_income_tax = bool(re.search(r'\b(income\s*-?\s*tax|direct\s*tax|itat|cbdt)\b', full_text, re.IGNORECASE))
        if has_uoi and has_income_tax:
            return True

        # Rule 3: Any additional user-defined keywords from environment variables
        if additional_keywords:
            for kw in additional_keywords:
                if kw and kw.strip() and kw.lower() in full_text:
                    return True

        return False

    def filter_judgments(self, judgments: List[Dict],
                         income_tax_keywords: List[str] = None,
                         final_judgment_keywords: List[str] = None,
                         exclude_keywords: List[str] = None,
                         max_days_old: Optional[int] = None) -> List[Dict]:
        """
        Filter judgments for final income tax judgments matching user requirements.
        """
        filtered = []

        # Calculate cutoff date if max_days_old is provided
        cutoff_date = None
        if max_days_old is not None and max_days_old > 0:
            now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
            cutoff_date = (now_ist - timedelta(days=max_days_old)).date()
            logger.info(f"Filtering judgments on or after cutoff date: {cutoff_date} (max {max_days_old} days old)")

        for judgment in judgments:
            # 1. Date Freshness
            if cutoff_date and judgment.get('parsed_date'):
                if judgment['parsed_date'] < cutoff_date:
                    continue

            # 2. Income Tax Requirement (Authority in party OR Union of India + Income Tax)
            if not self.is_income_tax_judgment(judgment, additional_keywords=income_tax_keywords):
                continue

            # 3. Final judgment keywords check
            if final_judgment_keywords:
                search_text = f"{judgment.get('title') or ''} {judgment.get('raw_text') or ''}".lower()
                final_match = any(kw.lower() in search_text for kw in final_judgment_keywords)
                if not final_match:
                    continue

            # 4. Exclusion check (interim/stay)
            if exclude_keywords:
                search_text = f"{judgment.get('title') or ''} {judgment.get('raw_text') or ''}".lower()
                if any(re.search(r'\b' + re.escape(ex.lower()) + r'\b', search_text) for ex in exclude_keywords):
                    continue

            filtered.append(judgment)

        return filtered

    def generate_judgment_id(self, judgment: Dict) -> str:
        """
        Generate a unique identifier for a judgment.
        Uses case number and date if available, otherwise falls back to a hash of the title.
        """
        case_number = (judgment.get('case_number') or '').strip()
        date = (judgment.get('date') or '').strip()

        if case_number and date:
            # Create a clean ID: remove special characters and spaces
            clean_case = re.sub(r'[^\w\-]', '', case_number)
            clean_date = re.sub(r'[^\w\-]', '', date)
            return f"{clean_case}_{clean_date}"
        else:
            # Fallback to hash of title
            return str(hash(judgment.get('title') or ''))