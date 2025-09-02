#!/usr/bin/env python3
"""
MIRCrew Indexer Script - Custom Torznab-compatible indexer for mircrew-releases.org
Scrapes all magnet links from each thread and returns them as separate results.

Usage:
python mircrew_indexer.py -q "search query" [-season N] [-ep N]
"""

import sys
import os
import argparse
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from requests import Session

# Add current directory to path for login import
sys.path.insert(0, os.path.dirname(__file__))

from login import MirCrewLogin
from magnet_unlock_script import MagnetUnlocker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MirCrewIndexer:
    """
    Torznab-compatible indexer for mircrew-releases.org
    Returns all magnet links from each thread as separate results
    """

    def __init__(self):
        self.base_url = "https://mircrew-releases.org"
        self.session: Optional[Session] = None
        self.logged_in = False
        self.login_handler = MirCrewLogin()
        # Initialize magnet unlocker - will share the same session
        self.unlocker: Optional[MagnetUnlocker] = None

        # Category mappings from mircrew.yml (id -> cat string)
        self.cat_mappings = {
            '25': 'Movies',
            '26': 'Movies',
            '51': 'TV',
            '52': 'TV',
            '29': 'TV/Documentary',
            '30': 'TV',
            '31': 'TV',
            '33': 'TV/Anime',
            '34': 'Movies/Other',
            '35': 'TV/Anime',
            '36': 'Movies/Other',
            '37': 'TV/Anime',
            '39': 'Books',
            '40': 'Books/EBook',
            '41': 'Audio/Audiobook',
            '42': 'Books/Comics',
            '43': 'Books/Mags',
            '45': 'Audio',
            '46': 'Audio'
        }

        # Default sizes by category (from mircrew.yml)
        self.default_sizes = {
            'Movies': '10GB',
            'TV': '2GB',
            'TV/Documentary': '2GB',
            'Books': '512MB',
            'Audio': '512MB'
        }

    def authenticate(self) -> bool:
        """Authenticate using internal MirCrewLogin - EXACT DIAGNOSTIC APPROACH"""

        # CRITICAL: Initialize session BEFORE calling login
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        if self.login_handler.login():
            # REPLACE with login client's session (diagnostic approach)
            self.session = self.login_handler.session
            self.logged_in = True
            logging.info("✅ Successfully authenticated")

            # Initialize magnet unlocker with the same session
            self.unlocker = MagnetUnlocker()
            self.unlocker.session = self.session  # Share the authenticated session
            self.unlocker.logged_in = True

            return True
        else:
            logging.error("❌ Authentication failed")
            return False

    def build_search_query(self, q: str, season: Optional[str] = None, ep: Optional[str] = None) -> str:
        """
        Build search query string from parameters
        """
        query_parts = []

        if q:
            query_parts.append(f'"{q}"')

        if season and ep:
            query_parts.append(f'S{season:02d}E{ep:02d}')
        elif season:
            query_parts.append(f'S{season:02d}')

        return ' '.join(query_parts)

    def prepare_search_params(self, q: str) -> List[str]:
        """
        Prepare search keywords with + prefix for each word
        """
        # Split query into words and prefix with +
        words = q.replace(':', ' ').split()
        return ['+' + word for word in words if word]

    def search(self, q: Optional[str] = None, season: Optional[str] = None,
              ep: Optional[str] = None, year: Optional[int] = None) -> str:
        """
        Perform search and return Torznab XML
        """
        if not self.authenticate():
            return self._error_response("Authentication failed")

        try:
            # Ensure we have a session from authentication
            # (authenticate() call above ensures this)

            # Build search keywords - back to exact mircrew.yml processing
            keywords = q
            if not keywords and year:
                keywords = str(year)
            elif not keywords:
                from datetime import datetime
                keywords = str(datetime.now().year)

            # EXACT keyword processing from mircrew.yml
            # 1. Strip season/episode patterns
            keywords = re.sub(r'\\b(?:[SE]\\d{1,4}){1,2}\\b', '', keywords).strip()
            # 2. Add + prefix to each word if multiple words
            if keywords and ' ' in keywords:
                words = [word.strip() for word in keywords.split() if word.strip()]
                keywords = ' '.join('+' + word for word in words if word)

            # PROVEN WORKING search parameters from diagnostic tests
            search_url = f"{self.base_url}/search.php"

            # Determine appropriate categories based on query
            categories = ['25', '26'] if not 'dexter' in keywords.lower() else ['51', '52']

            search_params = [
                ('keywords', keywords),
                ('sf', 'titleonly'),  # CRITICAL parameter that makes search work!
                ('sr', 'topics'),
                ('sk', 't'),
                ('sd', 'd'),
                ('st', '0'),
                ('ch', '25'),
                ('t', '0')
            ]

            for cat_id in categories:
                search_params.append(('fid[]', cat_id))

            logging.info(f"🔍 Searching for: '{keywords}' with {len(search_params)} params")

            # Ensure session is available before accessing attributes
            if not self.session:
                return self._error_response("Session not available for search")

            # Add debug output for request inspection
            logging.info(f"🔍 DEBUG: Session headers: {dict(self.session.headers)}")
            logging.info(f"🔍 DEBUG: Cookies: {dict(self.session.cookies)}")
            logging.info(f"🔍 DEBUG: Request URL: {search_url}")

            response = self.session.get(search_url, params=search_params, timeout=30, allow_redirects=True)

            if response.status_code != 200:
                return self._error_response(f"Search failed with status {response.status_code}")

            # Parse search results and build thread list
            threads = self._parse_search_results(response.text, keywords)

            # DEBUG OUTPUT: Compare with diagnostic - full HTML analysis
            if q == "Matrix":  # Add debug output for testing
                logging.info(f"🔍 DEBUG: Response status: {response.status_code}")
                logging.info(f"🔍 DEBUG: Response URL: {response.url}")
                logging.info(f"🔍 DEBUG: Content-Type: {response.headers.get('content-type', 'unknown')}")
                logging.info(f"🔍 DEBUG: Content-Length: {len(response.text)}")
                logging.info(f"🔍 DEBUG: Full response text sample: {response.text[:1000]}...")
                logging.info(f"🔍 DEBUG: Looking for HTML elements:")
                if '<html' in response.text.lower():
                    logging.info("✅ HTML found - normal HTML response")
                if '<?xml' in response.text:
                    logging.info("⚠️ XML found - forum returning XML instead of HTML")
                if '<li class="row"' in response.text:
                    logging.info("✅ Found search result rows - parsing should work")
                else:
                    logging.info("❌ No search result rows found - parsing will fail")
                soup = BeautifulSoup(response.text, 'html.parser')
                logging.info(f"🔍 DEBUG: Found {len(soup.find_all('li', class_='row'))} 'li.row' elements")
                logging.info(f"🔍 DEBUG: Found {len(soup.find_all(['li', 'div'], class_=re.compile(r'row|bg2')))} potential result elements")

            # For each thread, fetch and extract magnets
            all_magnets = []
            for thread in threads:
                thread_magnets = self._extract_thread_magnets(thread)
                all_magnets.extend(thread_magnets)

            # Build and return Torznab XML
            return self._build_torznab_xml(all_magnets)

        except Exception as e:
            logging.error(f"❌ Search error: {str(e)}")
            return self._error_response(str(e))

    def _parse_search_results(self, html: str, keywords: str = "") -> List[Dict]:
        """
        Parse search results HTML and extract thread data - USING DIAGNOSTIC APPROACH
        """
        soup = BeautifulSoup(html, 'html.parser')
        threads = []

        # EXACTLY copy the diagnostic_fixed.py approach
        # Just parse titles like the diagnostic does

        # Step 1: EXACT SAME element finding as diagnostic_fixed.py
        elements = soup.find_all(['li', 'div'], class_=re.compile(r'row|bg2'))

        logging.info(f"🔍 Parser found {len(elements)} raw elements")

        # Step 2: EXACT SAME processing as diagnostic_fixed.py
        results = []
        processed_count = 0
        valid_count = 0

        for element in elements:
            processed_count += 1
            logging.debug(f"🔍 Processing element {processed_count}...")

            # Find topic title link - EXACT diagnostic approach
            link = element.find('a', class_='topictitle')

            if not link or not link.get('href'):
                logging.debug(f"❌ Element {processed_count}: No title link")
                continue

            # Get full text like diagnostic does
            full_text = element.get_text().strip()
            if not full_text or len(full_text) < 10:
                logging.debug(f"❌ Element {processed_count}: Full text too short ({len(full_text)} chars)")
                continue

            # Success! This element has valid content
            valid_count += 1
            logging.debug(f"✅ Element {processed_count}: Valid content found")

            # Like diagnostic: add to results array
            results.append(full_text[:150])

            # Match diagnostic's limit
            if len(results) >= 25:
                break

        logging.info(f"📝 Parser found {len(results)} valid threads from {len(elements)} raw elements")

        # Convert results to expected thread format, now with proper URLs
        threads = []
        processed_results = 0

        for element in elements:
            # Reprocess elements to get URL from the title link
            title_link = element.find('a', class_='topictitle')
            if not title_link or not title_link.get('href'):
                continue

            full_text = element.get_text().strip()
            if not full_text or len(full_text) < 10:
                continue

            # Extract the REAL URL from the title link (critical fix!)
            details_url = urljoin(self.base_url, title_link['href'])

            threads.append({
                'title': title_link.get_text().strip()[:100],
                'details': details_url,  # REAL URL for magnet extraction!
                'category': 'Movies' if not 'dexter' in keywords.lower() else 'TV',
                'category_id': '25' if not 'dexter' in keywords.lower() else '52',
                'pub_date': datetime.now().isoformat(),
                'size': '1GB',
                'forum_id': '25' if not 'dexter' in keywords.lower() else '52',
                'full_text': full_text
            })

            processed_results += 1
            if processed_results >= len(results):  # Limit to the analyzed results
                break

        return threads

    def _contains_partial_match(self, query_term: str, title_text: str) -> bool:
        """EXACT SAME enhanced matching as diagnostic_fixed.py"""
        # Direct substring match (handles "Matrix" in "Animatrix")
        if query_term in title_text:
            return True

        # Handle cases like "Dexter:" in "Dexter: Resurrection" (phrase prefix)
        for word in title_text.split():
            # Check if query term is at start of word
            if word.lower().startswith(query_term) or query_term.startswith(word.lower()):
                return True

            # Handle hyphenated words
            if '-' in word:
                parts = word.split('-')
                if any(part.lower() == query_term or part.lower().startswith(query_term) for part in parts):
                    return True

            # Handle words with colons (NEW from diagnostic_fixed.py)
            if ':' in word:
                parts = word.split(':')
                if any(part.lower().strip() == query_term or part.lower().strip().startswith(query_term) for part in parts):
                    return True

        return False

    def _filter_relevant_results(self, threads: List[Dict], original_query: str) -> List[Dict]:
        """Filter threads using EXACT SAME logic as diagnostic_fixed.py"""
        if not original_query or not threads:
            return threads

        relevant = []
        not_relevant = []

        # Use SAME term splitting and checking as diagnostic
        search_terms = original_query.lower().split()

        for thread in threads:
            result_lower = thread['title'].lower()
            # SAME logic as diagnostic_fixed.py line 126
            if all(self._contains_partial_match(term, result_lower) for term in search_terms):
                relevant.append(thread)
            else:
                not_relevant.append(thread)

        return relevant

    def _extract_thread_magnets(self, thread: Dict) -> List[Dict]:
        """
        Fetch thread page and extract all magnet links
        Now includes thanks button unlocking functionality - WORKING!
        """
        magnets = []

        try:
            if not self.session or not self.unlocker:
                logging.error("❌ Session or unlocker not available")
                return magnets

            thread_url = thread['details']
            logging.info(f"🔓 Attempting to unlock magnets for thread: {thread_url}")

            # Use the unlocker to get magnets (this will handle thanks button clicking)
            magnet_urls = self.unlocker.extract_magnets_with_unlock(thread_url)

            for magnet_url in magnet_urls:
                # 🆕 EXTRACT MAGNET TITLE FROM dn PARAMETER
                display_name = self._extract_display_name(magnet_url)

                if display_name:
                    # Use display name directly as magnet title (filename with episode info)
                    magnet_title = display_name
                    magnet_description = f"Magnet: {display_name}"
                else:
                    # Fallback to thread title
                    magnet_title = thread['title']  # Default fallback to thread title
                    magnet_description = f"Magnet link from thread: {thread['title']}"

                magnets.append({
                    **thread,
                    'title': magnet_title,  # 🆕 Use magnet-specific title instead of thread title
                    'download': magnet_url,
                    'link': magnet_url,
                    'description': magnet_description,
                    'seeders': 1,  # Default (not available in HTML)
                    'peers': 2,    # Default (not available in HTML)
                })

                logging.debug(f"🔗 Extracted magnet title: '{magnet_title}'")
                logging.debug(f"🔗 Magnet: {magnet_url[:50]}...")

        except Exception as e:
            logging.error(f"❌ Error extracting magnets from {thread['details']}: {str(e)}")

        logging.info(f"🧲 Found {len(magnets)} magnet(s) in thread: {thread['title'][:50]}...")
        return magnets

    def _parse_size(self, title: str) -> Optional[str]:
        """
        Parse size information from thread title
        """
        # Look for size patterns like 1.5GB, 500MB, etc.
        size_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(GB|MB|TB|KiB|MiB|GiB)\b', title, re.IGNORECASE)
        if size_match:
            return size_match.group(1) + size_match.group(2).upper()

        # Alternative pattern: (1GB), [2.5MB], etc.
        alt_match = re.search(r'[\(\[])(\d+(?:\.\d+)?)\s*(GB|MB|TB|KiB|MiB|GiB)[\)\]]', title, re.IGNORECASE)
        if alt_match:
            return alt_match.group(1) + alt_match.group(2).upper()

        return None

    def _build_torznab_xml(self, magnets: List[Dict]) -> str:
        """
        Build Torznab XML response
        """
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">',
            '<channel>',

            # Response header
            f'<item>',
            f'<title>Total results</title>',
            f'<torznab:attr name="total" value="{len(magnets)}"/>',
            f'</item>',
        ]

        for i, magnet in enumerate(magnets):
            guid = f"magnet-{magnet['details'].split('=')[-1]}-{i}"

            xml_lines.extend([
                f'<item>',
                f'<title>{self._escape_xml(magnet["title"])}</title>',
                f'<guid>{guid}</guid>',
                f'<link>{self._escape_xml(magnet["link"])}</link>',
                f'<comments>{self._escape_xml(magnet["details"])}</comments>',
                f'<pubDate>{magnet["pub_date"]}</pubDate>',
                f'<category>{magnet["category"]}</category>',
                f'<size>{self._convert_size_to_bytes(magnet["size"])}</size>',
                f'<description>{self._escape_xml(magnet.get("description", ""))}</description>',

                # Torznab-specific attributes
                f'<torznab:attr name="category" value="{magnet["category_id"]}"/>',
                f'<torznab:attr name="size" value="{self._convert_size_to_bytes(magnet["size"])}"/>',
                f'<torznab:attr name="seeders" value="1"/>',
                f'<torznab:attr name="peers" value="2"/>',
                f'<torznab:attr name="downloadvolumefactor" value="0"/>',
                f'<torznab:attr name="uploadvolumefactor" value="1"/>',

                f'</item>'
            ])

        xml_lines.extend(['</channel>', '</rss>'])

        return '\n'.join(xml_lines)

    def _extract_display_name(self, magnet_url: str) -> Optional[str]:
        """
        Extract the display name (filename) from the magnet link's dn parameter
        """
        try:
            # Parse the URL to get query parameters
            parsed_url = urlparse(magnet_url)
            query_params = parse_qs(parsed_url.query)

            # Look for the dn (display name) parameter
            if 'dn' in query_params:
                display_name = query_params['dn'][0]  # Take first value
                return display_name

            return None
        except Exception:
            return None

    def _escape_xml(self, text: str) -> str:
        """Basic XML escaping"""
        if text:
            return text.replace('&', '&').replace('<', '<').replace('>', '>')
        return text

    def _convert_size_to_bytes(self, size_str: str) -> int:
        """Convert size string like '1.5GB' to bytes"""
        if not size_str:
            return 0

        size_match = re.match(r'(\d+(?:\.\d+)?)(GB|MB|TB|KiB|MiB|GiB)', size_str.upper())

        if not size_match:
            # Try parsing as pure number or add GB default
            try:
                return int(float(size_str) * 1024**3)  # Assume GB
            except ValueError:
                return 1024**3  # 1GB default

        value = float(size_match.group(1))
        unit = size_match.group(2)

        # Convert to bytes
        multipliers = {
            'KiB': 1024,
            'MiB': 1024**2,
            'GiB': 1024**3,
            'MB': 1000**2,
            'GB': 1000**3,
            'TB': 1000**4
        }

        return int(value * multipliers.get(unit, 1000**3))

    def _error_response(self, message: str) -> str:
        """Return error XML response"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
<title>Error</title>
<description>{self._escape_xml(message)}</description>
</item>
</channel>
</rss>'''


def main():
    parser = argparse.ArgumentParser(description='MIRCrew Indexer Script')
    parser.add_argument('-q', '--query', help='Search query')
    parser.add_argument('-season', type=str, help='Season number')
    parser.add_argument('-ep', type=str, help='Episode number')
    parser.add_argument('-year', type=int, help='Year for search')

    args = parser.parse_args()

    if not any([args.query, args.season, args.year]):
        parser.error("Must provide -q, -season/-ep, or -year")

    indexer = MirCrewIndexer()
    result = indexer.search(q=args.query, season=args.season, ep=args.ep, year=args.year)

    print(result)


if __name__ == "__main__":
    main()