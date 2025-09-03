import os
import re
import logging
import time
import random
from typing import Tuple, Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MirCrewLogin:
    """
    Handles authentication for mircrew-releases.org forum with enhanced anti-detection measures
    """

    def __init__(self):
        self.base_url = "https://mircrew-releases.org"
        self.login_url = f"{self.base_url}/ucp.php?mode=login&redirect=index.php"
        self.session = requests.Session()

        # Configure session headers with enhanced anti-detection
        self._setup_session_headers()

    def _setup_session_headers(self):
        """Setup session headers with rotating user agents"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]

        headers = {
            'User-Agent': random.choice(user_agents),
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
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }

        self.session.headers.update(headers)

    def get_credentials(self) -> Tuple[str, str]:
        """
        Retrieve username and password from environment variables
        """
        username = os.getenv('MIRCREW_USERNAME')
        password = os.getenv('MIRCREW_PASSWORD')

        logging.debug(f"Environment variables loaded: {bool(username)} / {bool(password) if password else False}")

        if not username or not password:
            raise ValueError("Missing credentials. Please set MIRCREW_USERNAME and MIRCREW_PASSWORD environment variables.")

        return username, password

    def _establish_session(self):
        """
        Establish a natural browsing session by visiting the homepage first
        """
        try:
            logging.info("Establishing browsing session...")
            # Visit main page first to get cookies and establish session
            response = self.session.get(f"{self.base_url}/index.php", allow_redirects=True, timeout=15)

            if response.status_code == 200:
                logging.info("Homepage visit successful")
                # Wait a moment to simulate human behavior
                time.sleep(random.uniform(0.5, 1.5))
            else:
                logging.warning(f"Homepage visit returned: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logging.warning(f"Error establishing session: {str(e)}")

    def _extract_form_data_precise(self, html_content: str) -> dict:
        """
        Precise form data extraction targeting the login form specifically
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        form_data = {}

        # Find the login form - try multiple strategies
        login_form = None

        # Strategy 1: Look for form with login action
        login_form = soup.find('form', action=lambda x: x and 'mode=login' in x)

        # Strategy 2: Look for form containing username input
        if not login_form:
            forms = soup.find_all('form')
            for form in forms:
                if form.find('input', {'name': 'username'}):
                    login_form = form
                    break

        # Strategy 3: Fallback to any form
        if not login_form:
            login_form = soup.find('form')

        if login_form:
            # Extract all inputs from the form
            inputs = login_form.find_all('input')
            for input_field in inputs:
                if hasattr(input_field, 'get'):
                    name = input_field.get('name')
                    value = input_field.get('value', '')
                    if name:
                        form_data[name] = value

        logging.debug(f"Extracted {len(form_data)} fields from login form")
        return form_data

    def _prepare_login_payload(self, username: str, password: str, form_data: dict) -> dict:
        """
        Prepare login payload with precise field ordering
        """
        payload = {}

        # Core login fields - these must be first
        payload['username'] = username
        payload['password'] = password
        payload['autologin'] = '1'
        payload['viewonline'] = '1'
        payload['login'] = 'Login'

        # Add hidden fields in specific order
        if 'sid' in form_data:
            payload['sid'] = form_data['sid']
        if 'form_token' in form_data:
            payload['form_token'] = form_data['form_token']
        if 'creation_time' in form_data:
            payload['creation_time'] = form_data['creation_time']
        if 'redirect' in form_data:
            payload['redirect'] = form_data['redirect']
        else:
            payload['redirect'] = 'index.php'

        return payload

    def login(self) -> bool:
        """
        Enhanced login with comprehensive anti-detection measures
        """
        try:
            logging.info("🟡 Starting MirCrew login process...")

            username, password = self.get_credentials()

            # Maximum attempts - increased for robustness
            max_attempts = 10

            for attempt in range(max_attempts):
                if attempt > 0:
                    # Progressive delay (2-5 seconds)
                    delay = random.uniform(2.0, 5.0)
                    logging.info(f"⏳ Waiting {delay:.1f}s before attempt {attempt + 1}/{max_attempts}")
                    time.sleep(delay)

                logging.info(f"🔄 Attempting login (attempt {attempt + 1}/{max_attempts})")

                # Establish natural session state (once per run)
                if attempt == 0:
                    self._establish_session()

                # Fresh session for each attempt
                if attempt > 0:
                    self.session = requests.Session()
                    self._setup_session_headers()
                    self._establish_session()

                try:
                    # Fetch login page with enhanced error handling
                    logging.info("📄 Fetching login page...")
                    response = self.session.get(self.login_url, allow_redirects=True, timeout=20)

                    if response.status_code != 200:
                        logging.warning(f"❌ Login page returned {response.status_code}")
                        continue

                except requests.exceptions.RequestException as e:
                    logging.warning(f"❌ Network error: {str(e)}")
                    continue

                # Extract form data precisely
                form_data = self._extract_form_data_precise(response.text)

                if not form_data.get('form_token'):
                    logging.warning("⚠️ Missing form_token, retrying...")
                    continue

                if not form_data.get('sid'):
                    logging.warning("⚠️ Missing sid, retrying...")
                    continue

                # Prepare payload
                login_payload = self._prepare_login_payload(username, password, form_data)

                logging.info(f"🚀 Submitting login as: {username}")

                # Submit with anti-detection timing
                time.sleep(random.uniform(0.5, 1.5))

                try:
                    login_response = self.session.post(
                        self.login_url,
                        data=login_payload,
                        allow_redirects=True,
                        timeout=20
                    )

                except requests.exceptions.RequestException as e:
                    logging.warning(f"❌ Login request failed: {str(e)}")
                    continue

                logging.info(f"📋 Response: {login_response.status_code} → {login_response.url}")

                # Validate login success
                success = self.validate_login(login_response)

                if success:
                    logging.info(f"✅ SUCCESS: Login completed on attempt {attempt + 1}")
                    return True

                # Enhanced error detection
                response_lower = login_response.text.lower()

                if 'il form inviato non è valido' in response_lower:
                    logging.warning("🔄 CSRF token expired, fresh retry needed")
                    continue
                elif any(error in response_lower for error in ['captcha', 'verification', 'robot']):
                    logging.warning("🤖 Anti-bot protection detected")
                    time.sleep(random.uniform(10, 20))  # Longer delay for anti-bot
                    continue
                elif any(error in response_lower for error in ['ban', 'suspended', 'blocked']):
                    logging.error("🚫 Account appears blocked/suspended")
                    return False
                elif 'modo manutenzione' in response_lower or 'maintenance' in response_lower:
                    logging.error("🛠️ Site is in maintenance mode")
                    return False
                else:
                    logging.warning("⚠️ Unknown error condition")

            # If we get here, all attempts failed
            logging.error(f"💀 LOGIN FAILED: All {max_attempts} attempts exhausted")
            return False

        except Exception as e:
            logging.error(f"💥 Critical login error: {str(e)}")
            return False

    def validate_login(self, response: requests.Response) -> bool:
        """
        Validate login success with multiple checks
        """
        try:
            if response.status_code != 200:
                logging.error(f"❌ Http error: {response.status_code}")
                return False

            response_lower = response.text.lower()

            # Check for error messages first
            soup = BeautifulSoup(response.text, 'html.parser')
            error_elements = []
            for tag in ['div', 'span', 'p']:
                for element in soup.find_all(tag):
                    element_class = element.get('class', [])
                    if element_class and any('error' in cls.lower() or 'danger' in cls.lower() for cls in element_class):
                        error_text = element.get_text().strip()
                        if error_text:
                            logging.error(f"📄 Website error: {error_text}")
                            error_elements.append(error_text.lower())

            # Error message checks
            failure_indicators = [
                'login unsuccessful',
                'invalid username',
                'wrong password',
                'authentication failed',
                'il nome utente',
                'la password',
                'accesso negato',
                'non autorizzato',
                'validation failed',
                'form not valid'
            ]

            for error in error_elements:
                if any(indicator in error for indicator in failure_indicators):
                    logging.error("❌ Login failed: credential error")
                    return False

            # Success checks
            if 'mode=login' not in response.url:
                logging.info("🔄 Redirected from login page")
                # Check for success content
                success_indicators = [
                    'logout',
                    'welcome',
                    'my account',
                    'profile',
                    'logged in as',
                    'benvenuto', # Italian "welcome"
                    'profilo'    # Italian "profile"
                ]

                for indicator in success_indicators:
                    if indicator in response_lower:
                        logging.info(f"✅ Login successful: {indicator}")
                        return True

                # If redirected to main content but no clear indicator, assume success
                if any(keyword in response_lower for keyword in ['forum', 'threads', 'posts', 'community']):
                    logging.info("✅ Login successful: main content detected")
                    return True

            # If still on login page with no clear errors, it failed
            if 'mode=login' in response.url or 'login.php' in response.url:
                logging.error("❌ Still on login page - authentication failed")
                return False

            # Default conservative approach
            logging.warning("⚠️ Unable to clearly determine login status")
            return False

        except Exception as e:
            logging.error(f"💥 Validation error: {str(e)}")
            return False

    def is_logged_in(self) -> bool:
        """
        Test if current session is still valid
        """
        try:
            response = self.session.get(f"{self.base_url}/index.php", allow_redirects=True)

            # Redirecting to login = not logged in
            if 'login' in response.url.lower():
                return False

            # Success indicators in response
            response_lower = response.text.lower()
            return any(indicator in response_lower for indicator in ['logout', 'my account', 'profile'])

        except Exception:
            return False

    def logout(self) -> bool:
        """
        Perform logout
        """
        try:
            logout_url = f"{self.base_url}/ucp.php?mode=logout&sid={self.session.cookies.get('phpbb3_34c6d_sid', '')}"
            response = self.session.get(logout_url, allow_redirects=True)
            logging.info("👋 Logged out successfully")
            return True
        except Exception as e:
            logging.error(f"Logout error: {str(e)}")
            return False


def test_login():
    """
    Comprehensive login test
    """
    logging.info("🧪 Starting MirCrew login test suite...")

    login_client = MirCrewLogin()
    start_time = time.time()

    success = login_client.login()

    if success:
        logging.info("🎉 TEST PASSED: Login successful")

        # Test session persistence
        logging.info("🧪 Testing session persistence...")
        if login_client.is_logged_in():
            logging.info("✅ Session persistence test PASSED")
        else:
            logging.warning("⚠️ Session persistence test FAILED")

        logging.info(".2f")
    else:
        logging.error("💀 TEST FAILED: Login unsuccessful")
        logging.info(".2f")

    return success


if __name__ == "__main__":
    test_login()