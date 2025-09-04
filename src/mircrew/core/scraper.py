#!/usr/bin/env python3
# FIXME: Phase 2 - BeautifulSoup typing needs comprehensive refactoring
"""
MIRCrew Forum Scraper - Standalone Python script that works out of the box
Scrapes all magnet links from each thread and returns them as separate results
"""

import sys
import os
import argparse
import re
import time
from typing import Optional, List, Dict, Any, Union, Set, cast
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PageElement

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .auth import MirCrewLogin

# Logging is now configured centrally in setup_logging() above

class MirCrewScraper:
    """
    Standalone MIRCrew forum scraper that works independently or with shared session
    """

    def __init__(self, shared_session: Optional[requests.Session] = None, user_agent: Optional[str] = None) -> None:
        """
        Initialize scraper with optional shared session for consistency.

        Args:
            shared_session: Session object from authentication (if available)
            user_agent: Custom user agent string (optional)
        """
        self.base_url = "https://mircrew-releases.org"

        # Use shared session if provided, otherwise create new one
        if shared_session:
            self.session = shared_session
            self.session_sharing = True
            logger.info("📋 Using shared authenticated session")
        else:
            # Use connection pooling with max 10 connections
            adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
            self.session = requests.Session()
            self.session.mount('https://', adapter)
            self.session.mount('http://', adapter)
            self.session_sharing = False
            # Set up browser-like headers if using own session
            default_ua = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            self._setup_session_headers(default_ua)
            # Initialize cache with 100 item capacity
            self.cache = {}
            self.cache_capacity = 100

        self.auth_handler: Optional[MirCrewLogin] = None
        self.max_retries = 3
        self.request_timeout = 30

    def _setup_session_headers(self, user_agent: str) -> None:
        """Setup session headers with realistic browser emulation"""
        self.session.headers.update({
            'User-Agent': user_agent,
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
        logger.debug(f"✅ Session headers configured with UA: {user_agent[:50]}...")

    def set_shared_session(self, session: requests.Session, login_handler: MirCrewLogin) -> bool:
        """
        Set a shared authenticated session to avoid re-authentication.

        Args:
            session: Authenticated session from MirCrew login
            login_handler: The login handler instance for session management
        """
        self.session = session
        self.auth_handler = login_handler
        self.session_sharing = True
        logger.info("📋 Shared session set successfully - authentication inherited")
        return True

    def authenticate(self, force: bool = False) -> bool:
        """
        Authenticate with the forum, skipping if using shared session.

        Args:
            force: Force new authentication even with shared session

        Returns:
            bool: True if authentication successful

        Raises:
            RuntimeError: If authentication fails
        """
        # Skip authentication if using shared session and not forced
        if self.session_sharing and not force:
            logger.info("🔄 Using shared authenticated session - skipping authentication")
            return True

        logger.info("🔐 Authenticating scraper session...")

        self.auth_handler = MirCrewLogin()
        if not self.auth_handler.login():
            error_msg = "Authentication failed - unable to establish session with MirCrew forum"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

        self.session = self.auth_handler.session

        # Only wait if we just authenticated (not shared)
        if not self.session_sharing:
            time.sleep(2)

        logger.info("✅ Authentication successful")
        return True

    def search_forum(self, query: str, max_results: int = 25, categories: Optional[List[str]] = None) -> str:
        """
        Main search function that finds threads and extracts magnets with enhanced error handling.

        Args:
            query: Search query string
            max_results: Maximum threads to process
            categories: List of category IDs to search (default: Movies and TV)

        Returns:
            str: Formatted results string

        Raises:
            RuntimeError: If authentication or search fails permanently
        """
        logger.info(f"🔍 Searching for: '{query}' (max: {max_results} results)")

        # Ensure we're authenticated
        self.authenticate()

        # Default categories focused on movies/TV
        if categories is None:
            categories = ['25', '26', '51', '52']  # Movies and TV categories

        search_params = [
            ('keywords', query),
            ('sf', 'titleonly'),       # CRITICAL: Title-only search (proven to work)
            ('sr', 'topics'),          # Return topics
            ('sk', 't'),               # Sort by time
            ('sd', 'd'),               # Most recent first
            ('st', '0'),               # All time periods
            ('ch', str(max(25, max_results))),  # Dynamic limit based on max_results
            ('t', '0')                 # Hidden field
        ]

        # Add category filters
        for cat_id in categories:
            search_params.append(('fid[]', cat_id))

        logger.info(f"📋 Searching {len(categories)} categories: {categories}")

        # Execute search with retry logic
        search_url = f"{self.base_url}/search.php"
        # Convert list of tuples to dict for type safety
        params_dict = dict(search_params)
        # Check cache first
        cache_key = f"search:{query}:{max_results}"
        if cache_key in self.cache:
            logger.info(f"📦 Returning cached results for '{query}'")
            return self.cache[cache_key]

        response = self._make_request_with_retry(search_url, params=params_dict,
                                                desc="search query", timeout=self.request_timeout)

        if not response or response.status_code != 200:
            error_msg = f"Search failed with HTTP status {response.status_code if response else 'N/A'}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

        # Parse search results
        try:
            threads = self._parse_search_page(response.text)
            logger.info(f"🎯 Found {len(threads)} threads in search results")
        except Exception as e:
            logger.error(f"❌ Failed to parse search results: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Search result parsing failed: {str(e)}")

        # Extract magnets from each thread (limit to max_results)
        threads_limited = threads[:max_results]
        all_magnets = []

        for i, thread in enumerate(threads_limited, 1):
            logger.info(f"🔗 Processing thread {i}/{len(threads_limited)}: {thread['title'][:60]}...")

            try:
                magnets = self._extract_thread_magnets(thread)
                logger.info(f"  └─ Found {len(magnets)} magnet(s) in thread")
                all_magnets.extend(magnets)
            except Exception as e:
                logger.warning(f"  └─ ⚠️ Failed to extract magnets from thread: {type(e).__name__}: {str(e)}")
                continue

        logger.info(f"🎉 Total results: {len(all_magnets)} magnet links from {len(threads_limited)} threads")

        results = self._format_results(all_magnets)
        
        # Update cache
        if len(self.cache) >= self.cache_capacity:
            self.cache.pop(next(iter(self.cache)))  # Remove oldest entry
        self.cache[cache_key] = results
        
        return results

    def _make_request_with_retry(self, url: str, method: str = 'GET', params: Optional[Dict[str, Any]] = None,
                                data=None, desc: str = "request", timeout: int = 30,
                                max_attempts: Optional[int] = None) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and exponential backoff.

        Args:
            url: Target URL
            method: HTTP method (GET/POST)
            params/data: Request parameters
            desc: Description for logging
            timeout: Request timeout
            max_attempts: Maximum retry attempts (uses self.max_retries if None)

        Returns:
            Response object or None if all attempts fail
        """
        if max_attempts is None:
            max_attempts = self.max_retries

        for attempt in range(max_attempts):
            try:
                logger.debug(f"🌐 Attempting {desc} (attempt {attempt + 1}/{max_attempts})")

                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=timeout, allow_redirects=True)
                else:
                    response = self.session.post(url, data=data, timeout=timeout, allow_redirects=True)

                # Only consider 2xx or 3xx as success (3xx followed by redirect)
                if response.status_code < 400:
                    logger.debug(f"✅ {desc.capitalize()} successful: {response.status_code}")
                    return response
                else:
                    logger.warning(f"⚠️ {desc.capitalize()} returned {response.status_code} (attempt {attempt + 1})")

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"⚠️ {desc.capitalize()} network error (attempt {attempt + 1}): {type(e).__name__}")
            except Exception as e:
                logger.error(f"❌ {desc.capitalize()} unexpected error (attempt {attempt + 1}): {type(e).__name__}: {str(e)}")
                if attempt < max_attempts - 1:
                    sleep_time = min(1.0 * (2 ** attempt), 10.0)  # Cap at 10 seconds
                    logger.debug(f"⏳ Retrying {desc} in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

        logger.error(f"💀 {desc.capitalize()} failed after {max_attempts} attempts")
        return None

    def _parse_search_page(self, html_content: str) -> List[Dict[str, str]]:
        """Parse the search results HTML to extract thread information"""

        soup = BeautifulSoup(html_content, 'html.parser')
        threads = []

        for row in soup.find_all('li', class_='row'):
            try:
                # FIXME: BeautifulSoup typing needs proper handling
                title_link = row.find('a', class_='topictitle')  # type: ignore[union-attr]
                if not title_link or not title_link.get('href'):  # type: ignore[union-attr]
                    continue

                title = title_link.get_text(strip=True)
                thread_url = urljoin(self.base_url, title_link['href'])  # type: ignore[index]

                # Extract other metadata
                category = "Movies"  # Default
                date_info = None

                # Try to extract date
                # FIXME: BeautifulSoup typing needs proper handling
                time_elem = row.find('time', {'datetime': True})  # type: ignore[union-attr]
                if time_elem:
                    date_info = time_elem.get('datetime')  # type: ignore[union-attr]

                threads.append({
                    'title': title,
                    'url': thread_url,
                    'category': category,
                    'date': date_info,
                    'id': thread_url.split('t=')[-1] if 't=' in thread_url else 'unknown'
                })

            except Exception as e:
                logger.debug(f"⚠️ Failed to parse thread row: {type(e).__name__}: {str(e)}")
                continue

        return threads

    def _extract_thread_magnets(self, thread_info: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Extract all magnet links from a thread with enhanced regex patterns and fallbacks.

        Args:
            thread_info: Thread information dictionary

        Returns:
            List of magnet information dictionaries
        """
        magnets: list[dict[str, Any]] = []
        found_magnets: set[str] = set()

        try:
            thread_url = thread_info.get('url', '')
            if not thread_url:
                logger.warning("⚠️ No URL provided for thread magnet extraction")
                return magnets

            logger.debug(f"📄 Fetching thread for magnet extraction: {thread_url}")

            # Use retry mechanism for thread fetching
            response = self._make_request_with_retry(thread_url, desc="thread fetch",
                                                   timeout=self.request_timeout)

            if not response or response.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch thread: HTTP {response.status_code if response else 'N/A'}")
                return magnets

            soup = BeautifulSoup(response.text, 'html.parser')
            logger.debug(f"✅ Thread page parsed successfully ({len(response.text)} chars)")

            # Enhanced magnet patterns with more variations
            magnet_patterns = [
                r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}',  # Standard 40-char hash
                r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32}',  # Shorter hash
                r'magnet:\?xt=urn:btih%3A[a-zA-Z0-9%]{40,}',  # URL-encoded
                r'magnet:\?[a-z]+=[^&]+&(?:.*&)*xt=urn:btih:[a-zA-Z0-9]{20,}',  # With parameters
                r'magnet:\?xt=urn:btih:[^\'"\s<>&]{32,}'  # More flexible matching
            ]

            # Search strategies ordered by reliability
            search_strategies = [
                ('direct_links', lambda: self._find_magnet_links(soup, magnet_patterns)),
                ('text_content', lambda: self._find_magnet_in_text(soup, magnet_patterns)),
                ('attributes', lambda: self._find_magnet_in_attributes(soup, magnet_patterns)),
                ('code_blocks', lambda: self._find_magnet_in_code(soup, magnet_patterns))
            ]

            for strategy_name, strategy_func in search_strategies:
                try:
                    magnets_found = strategy_func()
                    if magnets_found:
                        for magnet_url in magnets_found:
                            self._process_magnet_url(magnet_url, thread_info, magnets, found_magnets)
                        logger.debug(f"📋 {strategy_name}: found {len(magnets_found)} additional magnets")
                except Exception as e:
                    logger.debug(f"⚠️ Strategy {strategy_name} failed: {type(e).__name__}")

            logger.info(f"🧲 Extracted {len(magnets)} unique magnet(s) from thread")

        except Exception as e:
            logger.error(f"❌ Magnet extraction error for {thread_info.get('url', 'unknown')}: {type(e).__name__}: {str(e)}")

        return magnets

    def _find_magnet_links(self, soup: BeautifulSoup, patterns: List[str]) -> List[str]:
        """Find magnets in direct <a> tags"""
        magnets = []
        for pattern in patterns:
            for link in soup.find_all('a', href=re.compile(pattern, re.IGNORECASE)):
                # FIXME: Phase 2 - Refactor BeautifulSoup typing
                magnet_url = link.get('href', '').strip()  # type: ignore[union-attr]
                if magnet_url and self._is_valid_magnet(magnet_url):
                    magnets.append(magnet_url)
        return magnets

    def _find_magnet_in_text(self, soup: BeautifulSoup, patterns: List[str]) -> List[str]:
        """Find magnets in text content of various elements"""
        magnets = []
        text_elements = soup.find_all(['div', 'p', 'code', 'span', 'blockquote'])

        for element in text_elements:
            text_content = element.get_text()
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    if self._is_valid_magnet(match):
                        magnets.append(match)

        return magnets

    def _find_magnet_in_attributes(self, soup: BeautifulSoup, patterns: List[str]) -> List[str]:
        """Find magnets in HTML attributes like onclick, data-href, etc."""
        magnets = []
        attr_patterns = ['onclick', 'data-href', 'data-magnet', 'value']

        for attr in attr_patterns:
            for element in soup.find_all(attrs={attr: True}):
                # FIXME: Phase 2 - Refactor BeautifulSoup typing
                attr_value = element.get(attr, '')  # type: ignore[union-attr]
                for pattern in patterns:
                    # FIXME: Phase 2 - Ensure string type for regex
                    matches = re.findall(pattern, str(attr_value), re.IGNORECASE)
                    for match in matches:
                        if self._is_valid_magnet(match):
                            magnets.append(match)

        return magnets

    def _find_magnet_in_code(self, soup: BeautifulSoup, patterns: List[str]) -> List[str]:
        """Find magnets in <pre>, <code> blocks and forum code tags"""
        magnets = []
        code_elements = soup.find_all(['pre', 'code', 'div'], class_=re.compile(r'code|bbcode|forumcode'))

        for element in code_elements:
            text_content = element.get_text()
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    if self._is_valid_magnet(match):
                        magnets.append(match)

        return magnets

    def _is_valid_magnet(self, url: str) -> bool:
        """Validate magnet URL structure"""
        if not url or not isinstance(url, str):
            return False

        url_lower = url.lower().strip()

        # Basic structure check
        if not url_lower.startswith('magnet:'):
            return False

        # Must contain btih (BitTorrent Info Hash)
        if 'urn:btih:' not in url_lower:
            return False

        # Must have basic parameters
        if not re.search(r'xt=urn:btih:[a-zA-Z0-9]{20,}', url_lower):
            return False

        return True

    def _process_magnet_url(self, magnet_url: str, thread_info: Dict[str, str],
                          magnets: List[Dict[str, Any]], found_magnets: set) -> None:
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


    def _format_results(self, magnets: List[Dict[str, Any]]) -> str:
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


def main() -> None:
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