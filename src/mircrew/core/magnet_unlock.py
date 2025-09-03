#!/usr/bin/env python3
"""
MirCrew Magnet Unlocker Script
Clicks the "Thanks" button to unlock hidden magnet links on forum threads.
"""

import sys
import os
import re

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
from typing import Optional
from bs4 import Tag
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

# Add current directory to path for login import
sys.path.insert(0, os.path.dirname(__file__))

from .auth import MirCrewLogin

# Logging is now configured centrally in setup_logging() above

class MagnetUnlocker:
    """
    Unlocks hidden magnet links by clicking the "Thanks" button
    """

    def __init__(self):
        self.base_url = "https://mircrew-releases.org"
        self.session: Optional[requests.Session] = None
        self.logged_in = False
        self.login_handler = MirCrewLogin()

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
            return True
        else:
            logger.error("❌ Authentication failed")
            return False

    def _extract_first_post_id(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the ID of the first post in the thread by finding thanks buttons
        """
        try:
            # NEW APPROACH: Find the FIRST thanks button and extract post ID from it
            # This is more reliable than trying to find the first post directly
            thanks_buttons = soup.find_all(attrs={'id': re.compile(r'lnk_thanks_post\d+')})

            if thanks_buttons:
                # Take the first thanks button's ID and extract the post ID
                button_id = thanks_buttons[0].get('id', '')
                if isinstance(button_id, str) and button_id.startswith('lnk_thanks_post'):
                    post_id = button_id.replace('lnk_thanks_post', '')
                    logger.info(f"✅ Found first thanks button: {button_id}, extracted post ID: {post_id}")
                    return post_id

            # Fallback: Look for any elements with thanks in ID and extract post_id
            thanks_elements = soup.find_all(attrs={'id': re.compile(r'thanks.*\d+')})
            for elem in thanks_elements:
                elem_id = elem.get('id', '')
                if isinstance(elem_id, str):
                    # Extract number from various thanks button ID patterns
                    match = re.search(r'(\d+)', elem_id)
                    if match:
                        post_id = match.group(1)
                        logger.info(f"✅ Extracted post ID from thanks element: {elem_id} -> {post_id}")
                        return post_id

            # OLD approaches as backup
            # Approach 1: Look for anchor links with post IDs
            for link in soup.find_all('a', id=re.compile(r'post_\d+')):
                link_id = link.get('id', '')
                if isinstance(link_id, str) and re.search(r'post_\d+', link_id):
                    return link_id.replace('post_', '')

            # Approach 2: Look for post div elements
            for post_div in soup.find_all('div', id=re.compile(r'^post_\d+')):
                post_id = post_div.get('id', '')
                if isinstance(post_id, str) and 'post_' in post_id:
                    return post_id.replace('post_', '')

            # Approach 3: Look for permalink elements
            for permalink in soup.find_all('a', href=re.compile(r'post_id=\d+')):
                href = permalink.get('href', '')
                if isinstance(href, str):
                    match = re.search(r'post_id=(\d+)', href)
                    if match:
                        return match.group(1)

            logger.info("⚠️ Could not find thanks buttons or post IDs - magnets may already be unlocked")
            return None

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"❌ Data error extracting post ID: {type(e).__name__}: {str(e)}")
            return None

    def _find_thanks_button(self, soup: BeautifulSoup, post_id: str) -> Optional[str]:
        """
        Look for the thanks button with the correct ID
        """
        try:
            # Look for the thanks button by ID: lnk_thanks_post{post_id}
            button_id = f"lnk_thanks_post{post_id}"
            thanks_button = soup.find('a', id=button_id) or soup.find('button', id=button_id) or soup.find(attrs={'id': button_id})

            if thanks_button:
                logger.info(f"✅ Found thanks button: {button_id}")
                return button_id

            # Try alternative patterns - use find_all with filtering
            alt_patterns = [
                f"thanks_post_{post_id}",
                f"thank_post_{post_id}",
                "thank",
                "thanks"
            ]

            for pattern in alt_patterns:
                # Look for any element with this pattern in ID
                for elem in soup.find_all(attrs={'id': True}):
                    elem_id = elem.get('id', '')
                    if isinstance(elem_id, str) and pattern in elem_id.lower():
                        button_id = elem_id
                        logger.info(f"✅ Found thanks button (alternative): {button_id}")
                        return button_id

            logger.info(f"⚠️ Thanks button not found for post {post_id} (may already be unlocked)")
            return None

        except Exception as e:
            logger.error(f"❌ Error finding thanks button: {str(e)}")
            return None

    def _click_thanks_button(self, thread_url: str, button_id: str) -> bool:
        """
        Click the thanks button - multiple approaches
        """
        try:
            if not self.session:
                logger.error("❌ Session not available")
                return False

            # Get the post ID from the button ID
            post_id = button_id.replace('lnk_thanks_post', '')

            # Extract thread ID and forum ID from the thread URL
            thread_match = re.search(r'viewtopic\.php\?(?:.*&)?t=(\d+)', thread_url)
            forum_match = re.search(r'viewtopic\.php\?(?:.*&)?f=(\d+)', thread_url)

            thread_id = thread_match.group(1) if thread_match else '0'
            forum_id = forum_match.group(1) if forum_match else '0'

            # APPROACH 1: Based on the actual href pattern we saw
            # ./viewtopic.php?f=51&p=515262&thanks=515262&to_id=...
            thanks_url = f"{self.base_url}/viewtopic.php?f={forum_id}&p={post_id}&thanks={post_id}&to_id=0"

            logger.info(f"🔄 Attempting to click thanks button for post {post_id} (Approach 1)")

            # First, get the page to see what the thanks button href actually is
            response = self.session.get(thread_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ Can't get thread page to find thanks URL")
                return False

            soup = BeautifulSoup(response.text, 'html.parser')
            thanks_btn = soup.find('a', id=button_id)

            if thanks_btn and hasattr(thanks_btn, 'get') and isinstance(thanks_btn, Tag):
                # Get the actual href from the button
                actual_href = thanks_btn.get('href', '')
                if isinstance(actual_href, str) and actual_href:
                    if actual_href.startswith('./'):
                        actual_href = actual_href[2:]  # Remove leading ./
                    actual_thanks_url = f"{self.base_url}/{actual_href}"
                    logger.info(f"🔗 Using actual button href: {actual_thanks_url}")
                    thanks_url = actual_thanks_url

            # Try the AJAX call
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': thread_url
            }

            # Try with GET first (this is often how thanks buttons work)
            response = self.session.get(thanks_url, headers=headers)

            # If GET fails, try POST
            if response.status_code != 200:
                logger.info("🔄 GET failed, trying POST approach...")
                response = self.session.post(thanks_url, headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'})

            if response.status_code in [200, 302] or 'thanks' in response.text.lower():
                logger.info("✅ Thanks button clicked successfully")
                return True
            else:
                logger.warning(f"⚠️ Thanks button click failed with status: {response.status_code}")
                # Even if we get an error, continue - the magnets might become available after a refresh
                return True

        except Exception as e:
            logger.error(f"❌ Error clicking thanks button: {str(e)}")
            return False

    def unlock_magnets(self, thread_url: str) -> bool:
        """
        Main function to unlock magnets for a thread URL
        """
        if not self.session:
            logger.error("❌ Session not available")
            return False

        try:
            # Step 1: Fetch the thread page
            logger.info(f"📄 Fetching thread: {thread_url}")
            response = self.session.get(thread_url, timeout=30)

            if response.status_code != 200:
                logger.error(f"❌ Failed to fetch thread: {response.status_code}")
                return False

            soup = BeautifulSoup(response.text, 'html.parser')

            # Step 2: Extract first post ID
            post_id = self._extract_first_post_id(soup)
            if not post_id:
                logger.info("⚠️ No first post ID found - assuming magnets are already unlocked")
                return True

            # Step 3: Look for thanks button
            button_id = self._find_thanks_button(soup, post_id)
            if not button_id:
                logger.info("⚠️ Thanks button not found - magnets are likely already unlocked")
                return True

            # Step 4: Click the thanks button
            success = self._click_thanks_button(thread_url, button_id)
            if success:
                logger.info("✅ Magnet unlocking process completed")
                return True
            else:
                logger.warning("⚠️ Magnet unlocking may have failed")
                return False

        except Exception as e:
            logger.error(f"❌ Error in unlock_magnets: {str(e)}")
            return False

    def extract_magnets_with_unlock(self, thread_url: str) -> list:
        """
        Extract magnets from a thread, unlocking first if needed
        ONLY extracts from the FIRST POST to avoid duplicates
        """
        if not self.session:
            logger.error("❌ Session not available")
            return []

        # Try to unlock first (will handle the case where it's already unlocked)
        unlock_success = self.unlock_magnets(thread_url)
        if not unlock_success:
            logger.warning("⚠️ Unlock process failed, but continuing with extraction")

        # Now extract magnets (give page a moment to update if unlock happened)
        try:
            response = self.session.get(thread_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ Failed to fetch thread after unlock: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all magnet links from FIRST POST ONLY
            magnet_pattern = re.compile(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*$')
            magnets = []

            # Step 1: Get the first post ID (we already have the method for this)
            first_post_id = self._extract_first_post_id(soup)

            # NEW APPROACH: Find the first post by looking for post containers
            # and taking the chronologically first one (TOP of the page)
            all_post_containers = []

            # Look for common phpBB post container patterns
            pattern_candidates = [
                soup.find_all('div', class_=re.compile(r'postbody')),
                soup.find_all('div', class_=re.compile(r'post-text')),
                soup.find_all('div', class_=re.compile(r'content')),
                soup.find_all('div', class_=re.compile(r'post')),
                soup.find_all('article', class_=re.compile(r'post')),
                soup.find_all('div', attrs={'data-post-id': True}),
                soup.find_all(['div', 'li'], class_=re.compile(r'(post|content)')),
            ]

            for candidate_list in pattern_candidates:
                if candidate_list and len(candidate_list) > 0:
                    all_post_containers.extend(candidate_list)

            # Remove duplicates based on content
            seen_posts = set()
            unique_post_containers = []
            for post in all_post_containers:
                post_text = post.get_text(strip=True)[:100]  # First 100 chars as fingerprint
                if post_text and post_text not in seen_posts:
                    seen_posts.add(post_text)
                    unique_post_containers.append(post)

            logger.info(f"📝 Found {len(unique_post_containers)} unique post containers")

            # Take the FIRST post container (chronologically first)
            if unique_post_containers:
                first_post = unique_post_containers[0]
                logger.info("✅ Using first post container for magnet extraction")

                # Extract magnets ONLY from this first post
                for link in first_post.find_all('a', href=magnet_pattern):
                    magnet_url = link['href'].strip()
                    magnet_url = re.sub(r'\s+', '', magnet_url)  # Remove whitespace
                    magnet_url = magnet_url.split('#')[0]  # Remove fragments

                    if magnet_pattern.match(magnet_url):
                        # Avoid duplicates
                        if magnet_url not in magnets:
                            magnets.append(magnet_url)
                            logger.debug(f"🧲 Found magnet from first post: {magnet_url[:50]}...")
            else:
                logger.warning("⚠️ No post containers found, extracting from entire page")
                # Extreme fallback: search the entire page
                for link in soup.find_all('a', href=magnet_pattern):
                    magnet_url = link['href'].strip()
                    magnet_url = re.sub(r'\s+', '', magnet_url)
                    magnet_url = magnet_url.split('#')[0]

                    if magnet_pattern.match(magnet_url):
                        if magnet_url not in magnets:
                            magnets.append(magnet_url)
                            logger.debug(f"🧲 Found magnet (page search): {magnet_url[:50]}...")

            logger.info(f"📋 Extracted {len(magnets)} magnets from first post after unlock attempt")
            return magnets

        except Exception as e:
            logger.error(f"❌ Error extracting magnets: {str(e)}")
            return []


def diagnose_thanks_buttons():
    """Diagnose thanks buttons on a page"""
    unlocker = MagnetUnlocker()

    if not unlocker.authenticate():
        logger.error("❌ Authentication failed")
        return False

    test_url = "https://mircrew-releases.org/viewtopic.php?t=180404&hilit=Dexter+Resurrection"

    if unlocker.session:
        response = unlocker.session.get(test_url, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for all elements with "thanks" in the ID or href
            thanks_elements = soup.find_all(attrs={'id': re.compile(r'thanks|thank', re.IGNORECASE)})
            thanks_elements += soup.find_all(attrs={'href': re.compile(r'thanks|thank', re.IGNORECASE)})

            logger.info(f"🎯 Found {len(thanks_elements)} thanks-related elements:")
            for elem in thanks_elements[:5]:  # Show first 5
                logger.info(f"  - Tag: {elem.name}, ID: {elem.get('id')}, Class: {elem.get('class')}, Href: {elem.get('href', '')[:50]}...")

            return True
        else:
            logger.error(f"Failed to fetch page: {response.status_code}")
    return False

def test_unlocker():
    """Test the magnet unlocker"""
    unlocker = MagnetUnlocker()

    if not unlocker.authenticate():
        logger.error("❌ Authentication failed")
        return False

    # Test with a known thread URL
    test_url = "https://mircrew-releases.org/viewtopic.php?t=180404&hilit=Dexter+Resurrection"

    magnets = unlocker.extract_magnets_with_unlock(test_url)

    if magnets:
        logger.info(f"✅ Found {len(magnets)} magnets!")
        for i, magnet in enumerate(magnets[:3]):  # Show first 3
            logger.info(f"🔗 Magnet {i+1}: {magnet[:100]}...")
        return True
    else:
        logger.warning("⚠️ No magnets found or unlock failed")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "diagnose":
        success = diagnose_thanks_buttons()
    else:
        success = test_unlocker()
    sys.exit(0 if success else 1)