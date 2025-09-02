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

# Add current directory to path for login import
sys.path.insert(0, os.path.dirname(__file__))

from login import MirCrewLogin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MirCrewIndexer:
    """
    Torznab-compatible indexer for mircrew-releases.org
    Returns all magnet links from each thread as separate results
    """

    def __init__(self):
        self.base_url = "https://mircrew-releases.org"
        self.session = None
        self.logged_in = False

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
        """Authenticate using MirCrewLogin"""
        if self.logged_in:
            return True

        login_client = MirCrewLogin()

        if login_client.login():
            self.session = login_client.session
            self.logged_in = True
            logging.info("✅ Successfully authenticated")
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

            # EXACTLY replicate mircrew.yml search behavior
            search_url = f"{self.base_url}/search.php"

            # Try a minimal, clean search approach - just core parameters
            form_data = {
                'keywords': keywords,
                'sc': '0',           # No
                'sf': 'titleonly',   # Titles only
                'sr': 'topics',      # Topics
                'sk': 't',           # Sort by time
                'sd': 'd',           # Descending
                'st': '0',           # All time
                'ch': '300',         # Show 300
                't': '0'             # Hidden field
            }

            # Send ALL category IDs to maximize search coverage
            for cat_id in range(25, 47):  # Core range from mircrew.yml
                form_data[f'fid[]'] = str(cat_id)  # Each creates separate fid[] parameter
            for cat_id in selected_categories:
                form_data['fid[]'] = cat_id  # PHPBB expects multiple fid[] parameters

            logging.info(f"🔍 Searching for: '{keywords}' (GET with params)")
            logging.info(f"🔗 Form data: {form_data}")

            response = self.session.get(search_url, params=form_data, timeout=30, allow_redirects=True)

            if response.status_code != 200:
                return self._error_response(f"Search failed with status {response.status_code}")

            # Parse search results and build thread list
            threads = self._parse_search_results(response.text)

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

    def _parse_search_results(self, html: str) -> List[Dict]:
        """
        Parse search results HTML and extract thread data
        """
        soup = BeautifulSoup(html, 'html.parser')
        threads = []

        # logging.debug(f"🔍 Search page HTML preview: {html[:1000]}...")

        for row in soup.find_all('li', class_='row'):
            try:
                # Extract title and link
                title_link = row.find('a', class_='topictitle')
                if not title_link:
                    continue


                title = title_link.get_text(strip=True)
                details_url = urljoin(self.base_url, title_link['href'])

                # Extract category from forum link in row
                category_id = '25'  # Default to Movies
                try:
                    forum_link = row.find('a', href=re.compile(r'viewforum\.php\?f=\d+'))
                    if forum_link:
                        # Try to extract forum ID from href using simple string matching
                        href = forum_link.get('href', '')
                        f_match = re.search(r'viewforum\.php\?f=(\d+)', href)
                        if f_match:
                            category_id = f_match.group(1)
                except Exception as e:
                    # Silently continue with default if anything fails
                    pass

                category = self.cat_mappings.get(category_id, 'Movies')

                # Extract date from time element
                date_element = row.find('time', datetime=True)
                pub_date = date_element['datetime'] if date_element else datetime.now().isoformat()

                # Get default size for category
                size = self._parse_size(title)
                if not size:
                    size = self.default_sizes.get(category.split('/')[0], '1GB')

                threads.append({
                    'title': title,
                    'details': details_url,
                    'category': category,
                    'category_id': category_id,
                    'pub_date': pub_date,
                    'size': size,
                    'forum_id': category_id
                })

                if len(threads) >= 100:  # Limit results
                    break

            except Exception as e:
                logging.debug(f"⚠️ Error parsing thread (non-critical): {str(e)}")
                continue

        logging.info(f"📝 Found {len(threads)} threads in search results")
        return threads

    def _extract_thread_magnets(self, thread: Dict) -> List[Dict]:
        """
        Fetch thread page and extract all magnet links
        """
        magnets = []

        try:
            if not self.session:
                logging.error("❌ Session not available")
                return magnets

            response = self.session.get(thread['details'], timeout=30)

            if response.status_code != 200:
                logging.warning(f"⚠️ Failed to fetch thread {thread['details']}: {response.status_code}")
                return magnets

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all magnet links in post contents
            # PHPBB typically has div.post-text or div.content for post bodies
            magnet_pattern = re.compile(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*$')

            for post in soup.find_all('div', class_=re.compile(r'(post|content)')):
                for link in post.find_all('a', href=magnet_pattern):
                    magnet_url = link['href'].strip()

                    # Clean up magnet URL
                    magnet_url = re.sub(r'\s+', '', magnet_url)  # Remove whitespace
                    magnet_url = magnet_url.split('#')[0]  # Remove fragments

                    # Skip if invalid magnet
                    if not magnet_pattern.match(magnet_url):
                        continue

                    magnets.append({
                        **thread,  # Copy all thread metadata
                        'download': magnet_url,
                        'link': magnet_url,
                        'description': f"Magnet link from thread: {thread['title']}"
                    })

                    logging.debug(f"🔗 Extracted magnet: {magnet_url[:50]}...")

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