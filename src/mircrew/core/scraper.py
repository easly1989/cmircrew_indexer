#!/usr/bin/env python3
"""
MIRCrew Forum Scraper - Standalone Python script that works out of the box
Scrapes all magnet links from each thread and returns them as separate results
"""

import sys
import os
import argparse
import re

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Import login module
sys.path.insert(0, os.path.dirname(__file__))
from login import MirCrewLogin

# Logging is now configured centrally in setup_logging() above

class MirCrewScraper:
    """
    Standalone MIRCrew forum scraper that works independently
    """

    def __init__(self):
        self.base_url = "https://mircrew-releases.org"
        self.session = requests.Session()

        # Enhanced headers to look more like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })

    def authenticate(self):
        """Properly authenticate and wait for session stabilization"""
        print("🔐 Authenticating...")

        login_client = MirCrewLogin()
        if not login_client.login():
            raise Exception("Authentication failed")

        self.session = login_client.session

        # Wait and visit main page to stabilize session
        import time
        time.sleep(2)

        print("✅ Authentication successful")

    def search_forum(self, query, max_results=25):
        """Main search function that finds threads and extracts magnets"""

        print(f"🔍 Searching for: '{query}'")

        # Use EXACTLY the working parameters from diagnostic tests
        search_params = [
            ('keywords', query),
            ('sf', 'titleonly'),       # CRITICAL: Title-only search (proven to work)
            ('sr', 'topics'),          # Return topics
            ('sk', 't'),               # Sort by time
            ('sd', 'd'),               # Most recent first
            ('st', '0'),               # All time periods
            ('ch', '50'),              # Limit results to avoid overload
            ('t', '0')                 # Hidden field
        ]

        # Focus on Movies/TV categories where Matrix content would be
        categories_to_search = ['25', '26', '51', '52']  # Movies and TV categories
        for cat_id in categories_to_search:
            search_params.append(('fid[]', cat_id))

        print(f"📋 Using {len(categories_to_search)} categories in search")

        # Execute search
        search_url = f"{self.base_url}/search.php"
        response = self.session.get(search_url, params=search_params, timeout=30, allow_redirects=True)

        if response.status_code != 200:
            raise Exception(f"Search failed with status {response.status_code}")

        # Parse search results
        threads = self._parse_search_page(response.text)

        print(f"🎯 Found {len(threads)} threads in search results")

        # Extract magnets from each thread
        all_magnets = []
        for i, thread in enumerate(threads, 1):
            print(f"🔗 Processing thread {i}/{len(threads)}: {thread['title'][:60]}...")
            magnets = self._extract_thread_magnets(thread)
            print(f"  └─ Found {len(magnets)} magnet(s)")
            all_magnets.extend(magnets)

        print(f"🎉 Total results: {len(all_magnets)} magnet link(s)")

        return self._format_results(all_magnets)

    def _parse_search_page(self, html_content):
        """Parse the search results HTML to extract thread information"""

        soup = BeautifulSoup(html_content, 'html.parser')
        threads = []

        for row in soup.find_all('li', class_='row'):
            try:
                title_link = row.find('a', class_='topictitle')
                if not title_link or not title_link.get('href'):
                    continue

                title = title_link.get_text(strip=True)
                thread_url = urljoin(self.base_url, title_link['href'])

                # Extract other metadata
                category = "Movies"  # Default
                date_info = None

                # Try to extract date
                time_elem = row.find('time', {'datetime': True})
                if time_elem:
                    date_info = time_elem.get('datetime')

                threads.append({
                    'title': title,
                    'url': thread_url,
                    'category': category,
                    'date': date_info,
                    'id': thread_url.split('t=')[-1] if 't=' in thread_url else 'unknown'
                })

            except Exception as e:
                logging.debug(f"Failed to parse thread row: {e}")
                continue

        return threads

    def _extract_thread_magnets(self, thread_info):
        """Extract all magnet links from a thread"""

        magnets = []

        try:
            response = self.session.get(thread_info['url'], timeout=30)

            if response.status_code != 200:
                logging.warning(f"Failed to fetch thread: {response.status_code}")
                return magnets

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find ALL magnet links (be more aggressive)
            # Common patterns for magnet links
            magnet_patterns = [
                r'magnet:\?xt=urn:btih:',
                r'magnet:\?xt=urn:btih%'
            ]

            found_magnets = set()

            # Look in different places: links, text content, code blocks, etc.
            for pattern in magnet_patterns:
                # Search in all <a> tags with href attribute
                for link in soup.find_all('a', href=re.compile(pattern, re.IGNORECASE)):
                    magnet_url = link.get('href', '').strip()
                    if magnet_url and magnet_url.startswith('magnet:'):
                        self._process_magnet_url(magnet_url, thread_info, magnets, found_magnets)

                # Also search in text content that might contain magnet links
                for element in soup.find_all(['div', 'p', 'code'], class_=re.compile(r'.*')):
                    text_content = element.get_text()
                    # Look for magnet links in plain text
                    text_magnets = re.findall(r'magnet:\?xt=urn:btih:[^\'\"\s&]+', text_content)
                    for magnet_match in text_magnets:
                        if magnet_match.startswith('magnet:'):
                            self._process_magnet_url(magnet_match, thread_info, magnets, found_magnets)
"""
            # Also search in any element containing "magnet:"
            for element in soup.find_all(string=re.compile(r'magnet:\?xt=urn:btih', re.IGNORECASE)):
                # Extract the magnet URL from the parent element
                parent_a = element.find_parent('a')
                if parent_a and parent_a.get('href'):
                    magnet_url = parent_a.get('href', '').strip()
                    if magnet_url.startswith('magnet:'):
                        self._process_magnet_url(magnet_url, thread_info, magnets, found_magnets)

        except Exception as e:
            logging.error(f"Failed to extract magnets from thread {thread_info['url']}: {e}")

        return magnets

    def _process_magnet_url(self, magnet_url, thread_info, magnets, found_magnets):
        """Process and add a magnet URL to results"""
        # Clean up the magnet URL
        magnet_url = magnet_url.split('#')[0]  # Remove fragments
        magnet_url = re.sub(r'\s+', '', magnet_url)  # Remove whitespace

        # Only add if not already found
        if magnet_url not in found_magnets:
            found_magnets.add(magnet_url)

            magnets.append({
                'thread_title': thread_info['title'],
                'thread_url': thread_info['url'],
                'magnet_url': magnet_url,
                'thread_id': thread_info['id'],
                'category': thread_info['category']
            })

    def _format_results(self, magnets):
        """Format results as human-readable text"""

        except Exception as e:
            logging.error(f"Failed to extract magnets from thread {thread_info['url']}: {e}")

        return magnets

    def _format_results(self, magnets):
        """Format results as human-readable text"""

        output_lines = [
            "="*80,
            "MIRCrew Forum Scraper Results",
            "="*80,
            f"",
            f"Total magnet links found: {len(magnets)}",
            "",
        ]

        for i, magnet in enumerate(magnets, 1):
            output_lines.extend([
                f"MAGNET #{i}",
                f"Thread: {magnet['thread_title'][:80]}{'...' if len(magnet['thread_title']) > 80 else ''}",
                f"URL: {magnet['magnet_url'][:100]}" + ("..." if len(magnet['magnet_url']) > 100 else ""),
                f"Category: {magnet['category']}",
                f"Thread ID: {magnet['thread_id']}",
                "",
            ])

        output_lines.append("="*80)

        return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(description='MIRCrew Standalone Forum Scraper')
    parser.add_argument('query', help='Search query')
    parser.add_argument('-m', '--max', type=int, default=25, help='Maximum threads to process (default: 25)')

    args = parser.parse_args()

    try:
        scraper = MirCrewScraper()
        scraper.authenticate()
        results = scraper.search_forum(args.query, args.max)
        print(results)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()