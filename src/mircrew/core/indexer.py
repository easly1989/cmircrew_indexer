
"""
MIRCrew Indexer Script - Custom Torznab-compatible indexer for mircrew-releases.org
Scrapes all magnet links from each thread and returns them as separate results.

Usage:
python mircrew_indexer.py -q "search query" [-season N] [-ep N]
"""

import sys
import os
import argparse
import re
import yaml
from pathlib import Path

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
from datetime import datetime
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from requests import Session

from .auth import MirCrewLogin
from .magnet_unlock import MagnetUnlocker

# Logging is now configured centrally in setup_logging() above

class MirCrewIndexer:
    """
    Torznab-compatible indexer for mircrew-releases.org
    Returns all magnet links from each thread as separate results
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize indexer with config path.

        Args:
            config_path: Path to mircrew.yml config file (optional, defaults to project config)
        """
        self.base_url = "https://mircrew-releases.org"
        self.session: Optional[Session] = None
        self.logged_in = False
        self.login_handler = MirCrewLogin()
        # Initialize magnet unlocker - will share the same session
        self.unlocker: Optional[MagnetUnlocker] = None

        # Load configuration
        self.config_path = config_path or self._get_config_path()
        self.cat_mappings, self.default_sizes = self._load_config()

    def _get_config_path(self) -> str:
        """Get path to mircrew.yml config file."""
        # Try multiple possible paths
        possible_paths = [
            # Relative to current file
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'mircrew.yml'),
            # Relative to project root
            os.path.join(os.getcwd(), 'config', 'mircrew.yml'),
            # Absolute path for Docker
            '/app/config/mircrew.yml',
        ]

        for path in possible_paths:
            if os.path.isfile(path):
                logger.debug(f"Using config file: {path}")
                return path

        # Fallback: use current working directory
        fallback_path = os.path.join(os.getcwd(), 'config', 'mircrew.yml')
        logger.warning(f"Config file not found, using fallback: {fallback_path}")
        return fallback_path

    def _load_config(self) -> tuple:
        """
        Load category mappings and default sizes from config file.

        Returns:
            Tuple of (cat_mappings dict, default_sizes dict)
        """
        # Default fallback mappings
        cat_mappings = {
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

        default_sizes = {
            'Movies': '10GB',
            'TV': '2GB',
            'TV/Documentary': '2GB',
            'Books': '512MB',
            'Audio': '512MB'
        }

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if config and 'caps' in config and 'categorymappings' in config['caps']:
                loaded_mappings = {}

                # Build mappings from config categories
                for mapping in config['caps']['categorymappings']:
                    if isinstance(mapping, dict) and 'id' in mapping and 'cat' in mapping:
                        forum_id = str(mapping['id'])
                        category = mapping['cat']
                        loaded_mappings[forum_id] = category

                if loaded_mappings:
                    cat_mappings = loaded_mappings
                    logger.info(f"Loaded {len(loaded_mappings)} category mappings from config")

                # Extract size mappings from config if available
                if 'fields' in config and 'size_default' in config['fields']:
                    config_sizes = config['fields']['size_default']
                    if 'case' in config_sizes:
                        for case_rule, size in config_sizes['case'].items():
                            # Parse forum IDs from case rules like "a[href*=\"f=25\"]"
                            import re
                            match = re.search(r'f=(\d+)', case_rule)
                            if match and size:
                                forum_id = match.group(1)
                                # Convert category object to category id mapping
                                for mapping in config['caps']['categorymappings']:
                                    if isinstance(mapping, dict) and str(mapping.get('id', '')) == forum_id:
                                        # Set size for this category
                                        size_str = str(size)
                                        category_name = mapping.get('cat', '')
                                        if category_name in ['Movies', 'TV', 'Books', 'Audio'] and size_str:
                                            default_sizes[category_name] = size_str
                                        break

        except (FileNotFoundError, yaml.YAMLError, KeyError) as e:
            logger.warning(f"Failed to load config from {self.config_path}: {type(e).__name__}")
            logger.info("Using hardcoded fallback mappings")

        except Exception as e:
            logger.error(f"Unexpected error loading config: {type(e).__name__}: {str(e)}")
            logger.info("Using hardcoded fallback mappings")

        return cat_mappings, default_sizes

    def _extract_forum_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract forum ID from thread URL.

        Args:
            url: Thread URL like https://mircrew-releases.org/viewtopic.php?f=25&t=1234

        Returns:
            Forum ID string or None if not found
        """
        try:
            parsed_url = urlparse(url)
            query_params = dict(parse_qs(parsed_url.query))
            return query_params.get('f', [None])[0]
        except (ValueError, TypeError):
            logger.debug(f"Could not extract forum ID from URL: {url}")
            return None

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
            logger.info("✅ Successfully authenticated")

            # Initialize magnet unlocker with the same session
            self.unlocker = MagnetUnlocker()
            self.unlocker.session = self.session  # Share the authenticated session
            self.unlocker.logged_in = True

            return True
        else:
            logger.error("❌ Authentication failed")
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
        Supports direct thread searching with syntax: thread::{Thread_Number}
        """
        if not self.authenticate():
            return self._error_response("Authentication failed")

        try:
            # Ensure we have a session from authentication
            # (authenticate() call above ensures this)

            # Check for direct thread search syntax: thread::{Thread_Number}
            if q and q.lower().startswith("thread::"):
                return self._search_thread_by_id(q)

            # Build search keywords - back to exact mircrew.yml processing
            keywords = q
            if not keywords and year:
                keywords = str(year)
            elif not keywords:
                from datetime import datetime
                keywords = str(datetime.now().year)

            # EXACT keyword processing from mircrew.yml
            # 1. Strip season/episode patterns
            keywords = re.sub(r'\b(?:[SE]\d{1,4}){1,2}\b', '', keywords).strip()
            # 2. Add + prefix to each word if multiple words
            if keywords and ' ' in keywords:
                words = [word.strip() for word in keywords.split() if word.strip()]
                keywords = ' '.join('+' + word for word in words if word)

            # REVERT TO WORKING DIAGNOSTIC SEARCH PARAMETERS
            search_url = f"{self.base_url}/search.php"

            # Determine appropriate categories based on query content
            # Use both Movie and TV categories by default for broader results
            # Category IDs from mircrew.yml: 25=Movies/SD, 26=Movies/HD, 51=TV/SD, 52=TV/HD
            categories = ['25', '26', '51', '52']  # Search both Movies and TV by default

            # If specific category is requested through cat parameter, filter accordingly
            # But for now, search broadly to avoid missing results

            search_params = [
                ('keywords', keywords),
                ('sf', 'titleonly'),  # CRITICAL parameter that makes search work!
                ('sr', 'topics'),
                ('sk', 't'),
                ('sd', 'd'),
                ('st', '0'),
            ]

            for cat_id in categories:
                search_params.append(('fid[]', cat_id))

            logger.info(f"🔍 Searching for: '{keywords}' with {len(search_params)} params")

            # Ensure session is available before accessing attributes
            if not self.session:
                return self._error_response("Session not available for search")
    
            # Enhanced error handling with better error messages
            try:
                response = self.session.get(search_url, params=search_params, timeout=30, allow_redirects=True)
            except requests.exceptions.Timeout:
                logger.error("⏱️ Request timed out after 30 seconds")
                raise ConnectionError("Request timed out - forum may be overloaded")
            except requests.exceptions.ConnectionError:
                logger.error("🔌 Connection error - unable to reach forum")
                raise ConnectionError("Unable to connect to MirCrew forum - check network connectivity")

            if response.status_code != 200:
                return self._error_response(f"Search failed with status {response.status_code}")

            # Parse search results and build thread list
            threads = self._parse_search_results(response.text, keywords)

            # DEBUG OUTPUT: Compare with diagnostic - full HTML analysis
            if q == "Matrix":  # Add debug output for testing
                logger.info(f"🔍 DEBUG: Response status: {response.status_code}")
                logger.info(f"🔍 DEBUG: Response URL: {response.url}")
                logger.info(f"🔍 DEBUG: Content-Type: {response.headers.get('content-type', 'unknown')}")
                logger.info(f"🔍 DEBUG: Content-Length: {len(response.text)}")
                logger.info(f"🔍 DEBUG: Full response text sample: {response.text[:1000]}...")
                logger.info(f"🔍 DEBUG: Looking for HTML elements:")
                if '<html' in response.text.lower():
                    logger.info("✅ HTML found - normal HTML response")
                if '<?xml' in response.text:
                    logger.info("⚠️ XML found - forum returning XML instead of HTML")
                if '<li class="row"' in response.text:
                    logger.info("✅ Found search result rows - parsing should work")
                else:
                    logger.info("❌ No search result rows found - parsing will fail")
                soup = BeautifulSoup(response.text, 'html.parser')
                logger.info(f"🔍 DEBUG: Found {len(soup.find_all('li', class_='row'))} 'li.row' elements")
                logger.info(f"🔍 DEBUG: Found {len(soup.find_all(['li', 'div'], class_=re.compile(r'row|bg2')))} potential result elements")

            # For each thread, fetch and extract magnets
            all_magnets = []
            for thread in threads:
                # Set category ID based on loaded config
                if 'forum_id' in thread and str(thread['forum_id']) in self.cat_mappings:
                    thread['category_id'] = thread['forum_id']

                # Apply size defaults based on loaded config
                if thread.get('category') in self.default_sizes:
                    thread['size'] = self.default_sizes[thread['category']]

                thread_magnets = self._extract_thread_magnets(thread)
                all_magnets.extend(thread_magnets)

            # Build and return Torznab XML
            return self._build_torznab_xml(all_magnets)

        except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
            logger.error(f"❌ Network error during search: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Network error: {type(e).__name__}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"❌ Data validation error during search: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Data validation error: {type(e).__name__}")
        except Exception as e:
            logger.error(f"❌ Unexpected search error: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Unexpected error: {type(e).__name__}")

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

        logger.info(f"🔍 Parser found {len(elements)} raw elements")

        # Step 2: EXACT SAME processing as diagnostic_fixed.py
        results = []
        processed_count = 0
        valid_count = 0

        for element in elements:
            processed_count += 1
            logger.debug(f"🔍 Processing element {processed_count}...")

            # Find topic title link - EXACT diagnostic approach
            link = element.find('a', class_='topictitle')

            if not link or not link.get('href'):
                logger.debug(f"❌ Element {processed_count}: No title link")
                continue

            # Get full text like diagnostic does
            full_text = element.get_text().strip()
            if not full_text or len(full_text) < 10:
                logger.debug(f"❌ Element {processed_count}: Full text too short ({len(full_text)} chars)")
                continue

            # Success! This element has valid content
            valid_count += 1
            logger.debug(f"✅ Element {processed_count}: Valid content found")

            # Like diagnostic: add to results array
            results.append(full_text[:150])

            # Match diagnostic's limit
            if len(results) >= 25:
                break

        logger.info(f"📝 Parser found {len(results)} valid threads from {len(elements)} raw elements")

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

            # Extract forum ID from URL to determine category
            forum_id = self._extract_forum_id_from_url(details_url)
            category = self.cat_mappings.get(str(forum_id), 'TV')
            category_id = str(forum_id) if forum_id else '52'

            # Apply size defaults from config
            default_size = self.default_sizes.get(category, '1GB')

            threads.append({
                'title': title_link.get_text().strip()[:100],
                'details': details_url,  # REAL URL for magnet extraction!
                'category': category,
                'category_id': category_id,
                'pub_date': datetime.now().isoformat(),
                'size': default_size,  # Use config-based size defaults
                'forum_id': forum_id,
                'full_text': full_text
            })

            processed_results += 1
            if processed_results >= len(results):  # Limit to the analyzed results
                break

        return threads

    def _search_thread_by_id(self, query: str) -> str:
        """
        Search for specific thread by ID using syntax: thread::{Thread_Number}
        Example: thread::180404
        """
        try:
            # Parse thread ID from query: thread::180404 -> 180404
            if not query.lower().startswith("thread::"):
                return self._error_response("Invalid thread search syntax. Use: thread::{number}")

            thread_id = query[8:]  # Remove "thread::" prefix

            # Validate thread ID format
            if not thread_id.isdigit():
                return self._error_response(f"Invalid thread ID: {thread_id}. Must be numeric.")

            logger.info(f"🔍 Direct thread search for ID: {thread_id}")

            # Construct thread URL
            thread_url = f"{self.base_url}/viewtopic.php?t={thread_id}"

            # Try to get category info from first post (will be updated when magnet is fetched)
            # For now use TV defaults which covers most content
            category_id = '52'  # TV default
            category = 'TV'

            thread_data = {
                'title': f"Thread {thread_id}",
                'details': thread_url,
                'category': category,
                'category_id': category_id,
                'pub_date': datetime.now().isoformat(),
                'size': self.default_sizes.get(category, '2GB'),  # Use config default
                'forum_id': category_id
            }

            # Extract magnets from this specific thread
            all_magnets = self._extract_thread_magnets(thread_data)

            # Build and return Torznab XML for direct thread search
            xml_lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">',
                '<channel>',

                # No header item for direct thread search - just proceed with magnets
            ]

            for i, magnet in enumerate(all_magnets):
                guid = f"thread-{thread_id}-{i}"

                # Calculate size in bytes for enclosure
                size_bytes = self._convert_size_to_bytes(magnet["size"])
    
                # Extract magnet hash and create HTTP download URL
                magnet_hash = self._extract_magnet_hash(magnet["link"])
                download_url = f"http://mircrew-indexer:9118/download/{magnet_hash}"
    
                # Properly escape all XML content
                title_escaped = self._escape_xml(magnet["title"])
                link_escaped = self._escape_xml(magnet["link"])
                details_escaped = self._escape_xml(magnet["details"])
                category_escaped = self._escape_xml(magnet["category"])
                description_escaped = self._escape_xml(magnet.get("description", ""))
    
                xml_lines.extend([
                    f'<item>',
                    f'<title>{title_escaped}</title>',
                    f'<guid>{guid}</guid>',
                    f'<link>{link_escaped}</link>',
                    f'<enclosure url="{download_url}" type="application/x-bittorrent" length="{size_bytes}"/>',
                    f'<comments>{details_escaped}</comments>',
                    f'<pubDate>{magnet["pub_date"]}</pubDate>',
                    f'<category>{category_escaped}</category>',
                    f'<size>{size_bytes}</size>',
                    f'<description>{description_escaped}</description>',
    
                    # Torznab-specific attributes
                    f'<torznab:attr name="category" value="{magnet["category_id"]}"/>',
                    f'<torznab:attr name="size" value="{size_bytes}"/>',
                    f'<torznab:attr name="seeders" value="1"/>',
                    f'<torznab:attr name="peers" value="2"/>',
                    f'<torznab:attr name="downloadvolumefactor" value="0"/>',
                    f'<torznab:attr name="uploadvolumefactor" value="1"/>',
    
                    f'</item>'
                ])

            xml_lines.extend(['</channel>', '</rss>'])

            xml_output = '\n'.join(xml_lines)
            logger.info(f"📊 Direct thread search complete: {len(all_magnets)} magnets from thread {thread_id}")
            return xml_output

        except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
            logger.error(f"❌ Network error in direct thread search: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Network error searching thread: {type(e).__name__}")
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Validation error in direct thread search: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Validation error searching thread: {type(e).__name__}")
        except Exception as e:
            logger.error(f"❌ Unexpected error in direct thread search: {type(e).__name__}: {str(e)}")
            return self._error_response(f"Unexpected error searching thread: {type(e).__name__}")

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
                logger.error("❌ Session or unlocker not available")
                return magnets

            thread_url = thread['details']
            if not thread_url or not isinstance(thread_url, str):
                logger.error("❌ Invalid thread URL format")
                return magnets

            logger.info(f"🔓 Attempting to unlock magnets for thread: {thread_url}")

            # Use the unlocker to get magnets (this will handle thanks button clicking)
            magnet_urls = self.unlocker.extract_magnets_with_unlock(thread_url)

            if not isinstance(magnet_urls, list):
                logger.error(f"❌ Invalid magnet URLs returned from unlocker: {type(magnet_urls)}")
                return magnets

            for magnet_url in magnet_urls:
                # Validation check for magnet URL
                if not isinstance(magnet_url, str) or not magnet_url.startswith('magnet:'):
                    logger.debug(f"⚠️ Skipping invalid magnet URL: {magnet_url[:50]}...")
                    continue

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

                logger.debug(f"🔗 Extracted magnet title: '{magnet_title}'")
                logger.debug(f"🔗 Magnet: {magnet_url[:50]}...")

        except (requests.exceptions.RequestException, ValueError, TypeError, AttributeError) as e:
            logger.error(f"❌ Error extracting magnets from {thread.get('details', 'unknown')}: {type(e).__name__}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error extracting magnets from {thread.get('details', 'unknown')}: {type(e).__name__}: {str(e)}")

        logger.info(f"🧲 Found {len(magnets)} magnet(s) in thread: {thread['title'][:50]}...")
        return magnets

    def _parse_size(self, title: str) -> Optional[str]:
        """
        Parse size information from thread title with enhanced patterns.

        Args:
            title: Thread title to parse

        Returns:
            Size string (e.g., '1.5GB', '500MB') or None if not found
        """
        if not title:
            return None

        # Patterns ordered by specificity (most specific first)
        patterns = [
            # Standard format: 1.5GB, 500MB, etc.
            r'\b(\d+(?:[\.,]\d{1,2})?)\s*(GB|MB|TB|KiB|MiB|GiB|B)\b',
            # With parentheses: (1.5GB), [500MB]
            r'[\(\[\{](\d+(?:[\.,]\d{1,2})?)\s*(GB|MB|TB|KiB|MiB|GiB|B)[\)\]\}]',
            # Italian format: 1,5 GB, 500 MB
            r'\b(\d+[\.,]\d{1,2})\s*(GB|MB|TB|KiB|MiB|GiB|B)\b',
            # Simple bytes: 1024MB
            r'(\d+(?:[\.,]\d{1,2})?)(GB|MB|TB|KiB|MiB|GiB|B)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, title, re.IGNORECASE)
            if matches:
                # Take the first match and normalize
                size_num, size_unit = matches[0]
                size_unit = size_unit.upper()

                # Normalize Italian decimal separator
                size_num = size_num.replace(',', '.')

                # Handle 'B' suffix (assume MB if no unit)
                if size_unit == 'B':
                    size_unit = 'MB'

                return f"{size_num}{size_unit}"

        return None

    def _build_torznab_xml(self, magnets: List[Dict]) -> str:
        """
        Build Torznab XML response
        """
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">',
            '<channel>',
        ]

        for i, magnet in enumerate(magnets):
            guid = f"magnet-{magnet['details'].split('=')[-1]}-{i}"

            # Calculate size in bytes for enclosure
            size_bytes = self._convert_size_to_bytes(magnet["size"])

            # Extract magnet hash and create HTTP download URL
            magnet_hash = self._extract_magnet_hash(magnet["link"])
            download_url = f"http://mircrew-indexer:9118/download/{magnet_hash}"

            # Properly escape all XML content in direct thread search
            title_escaped = self._escape_xml(magnet["title"])
            link_escaped = self._escape_xml(magnet["link"])
            details_escaped = self._escape_xml(magnet["details"])
            category_escaped = self._escape_xml(magnet["category"])
            description_escaped = self._escape_xml(magnet.get("description", ""))

            xml_lines.extend([
                f'<item>',
                f'<title>{title_escaped}</title>',
                f'<guid>{guid}</guid>',
                f'<link>{link_escaped}</link>',
                f'<enclosure url="{download_url}" type="application/x-bittorrent" length="{size_bytes}"/>',
                f'<comments>{details_escaped}</comments>',
                f'<pubDate>{magnet["pub_date"]}</pubDate>',
                f'<category>{category_escaped}</category>',
                f'<size>{size_bytes}</size>',
                f'<description>{description_escaped}</description>',

                # Torznab-specific attributes
                f'<torznab:attr name="category" value="{magnet["category_id"]}"/>',
                f'<torznab:attr name="size" value="{size_bytes}"/>',
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
            if not isinstance(magnet_url, str) or not magnet_url:
                return None

            # Parse the URL to get query parameters
            parsed_url = urlparse(magnet_url)
            if parsed_url.scheme != 'magnet':
                logger.debug(f"⚠️ Not a magnet URL: {magnet_url[:50]}...")
                return None

            query_params = parse_qs(parsed_url.query)

            # Look for the dn (display name) parameter
            if 'dn' in query_params:
                display_name = query_params['dn'][0]  # Take first value
                if isinstance(display_name, str) and display_name.strip():
                    return display_name.strip()

            return None
        except (ValueError, TypeError) as e:
            logger.debug(f"⚠️ Error parsing display name from magnet URL: {type(e).__name__}")
            return None

    def _extract_magnet_hash(self, magnet_url: str) -> str:
        """Extract 40-character btih hash from magnet URL"""
        try:
            if not isinstance(magnet_url, str) or not magnet_url:
                logger.warning("⚠️ Invalid magnet URL provided for hash extraction")
                return ""

            if not magnet_url.startswith('magnet:'):
                logger.warning(f"⚠️ Not a magnet URL: {magnet_url[:50]}...")
                return ""

            import urllib.parse
            parsed = urllib.parse.urlparse(magnet_url)
            query_params = urllib.parse.parse_qs(parsed.query)

            if 'xt' in query_params:
                xt_param = query_params['xt'][0]
                if isinstance(xt_param, str) and xt_param.startswith('urn:btih:'):
                    btih_hash = xt_param.split(':')[2][:40]
                    if len(btih_hash) == 40 and btih_hash.isalnum():
                        return btih_hash
                    else:
                        logger.warning(f"⚠️ Invalid btih hash format: {btih_hash}")

            logger.warning(f"⚠️ No valid btih parameter found in: {magnet_url[:100]}...")
            return ""
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Error extracting magnet hash: {type(e).__name__}: {str(e)}")
            return ""

    def _escape_xml(self, text: str) -> str:
        """Basic XML escaping"""
        if not text:
            return ""
        # XML entity replacements in correct order
        replacements = [('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'), ('"', '&quot;'), ("'", '&apos;')]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    def _convert_size_to_bytes(self, size_str: str) -> int:
        """
        Convert size string to bytes with comprehensive unit support.

        Args:
            size_str: Size string like '1.5GB', '500MB', etc.

        Returns:
            Size in bytes as integer
        """
        if not size_str or not isinstance(size_str, str):
            return 1073741824  # Default to 1GB

        # Clean the string and extract components
        size_str = size_str.upper().strip()

        # Handle Italian decimal separator
        size_str = size_str.replace(',', '.')

        # Comprehensive unit mapping with both decimal (1000^x) and binary (1024^x) variants
        multipliers = {
            # Binary units ( power of 2 )
            'KIB': 1024,
            'MIB': 1024**2,
            'GIB': 1024**3,
            'TIB': 1024**4,

            # Decimal units ( power of 10 )
            'KB': 10**3,
            'MB': 10**6,
            'GB': 10**9,
            'TB': 10**12,

            # Legacy units (assuming decimal)
            'K': 10**3,
            'M': 10**6,
            'G': 10**9,
            'T': 10**12,

            # Special cases
            'B': 1,       # Just bytes
        }

        # Match number and unit
        match = re.match(r'^(\d+(?:\.\d+)?)([KMGT]I?B?)?$', size_str)

        if match:
            value_str, unit = match.groups()
            value = float(value_str)

            if unit and unit in multipliers.keys():
                multiplier = multipliers[unit]
            elif unit:
                # Unknown unit, assume it's bytes if just a number
                logger.debug(f"Unknown unit '{unit}', treating as bytes")
                multiplier = 1
            else:
                # No unit specified, assume GB for large numbers, MB for smaller
                multiplier = (10**9 if value < 1000 else 10**6)

            try:
                result = int(value * multiplier)
                return max(result, 1)  # Ensure at least 1 byte
            except (OverflowError, ValueError):
                logger.warning(f"Size conversion overflow for '{size_str}', using default 1GB")
                return 1073741824

        # We couldn't parse the size, try to extract a number and assume GB
        try:
            # Look for any number in the string
            number_match = re.search(r'(\d+(?:\.\d+)?)', size_str)
            if number_match:
                value = float(number_match.group(1))
                # Assume GB for large numbers, MB for smaller
                multiplier = 10**9 if value < 100 else 10**6
                return int(value * multiplier)
        except (ValueError, OverflowError):
            pass

        # Final fallback
        logger.warning(f"Could not parse size string '{size_str}', using default 1GB")
        return 1073741824

    def _error_response(self, message: str) -> str:
        """Return error XML response"""
        escaped_message = self._escape_xml(message)
        xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
<title>Error</title>
<description>{}</description>
</item>
</channel>
</rss>"""
        return xml_template.format(escaped_message)


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