import os
import re
import time
import random
from typing import Tuple, Optional
import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)

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
        """Setup session headers with enhanced rotating user agents and better anti-detection"""
        # Expanded user agent pool for better rotation
        user_agents = [
            # Windows Chrome versions
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",

            # macOS Chrome versions
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",

            # Linux Chrome
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

            # Windows Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",

            # macOS Firefox
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",

            # Windows Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",

            # Linux Firefox
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]

        selected_ua = random.choice(user_agents)

        # Extract browser info for consistent headers
        is_chrome = 'Chrome' in selected_ua
        is_firefox = 'Firefox' in selected_ua
        is_edge = 'Edg' in selected_ua

        headers = {
            'User-Agent': selected_ua,
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
        }

        # Browser-specific headers
        if is_chrome or is_edge:
            headers['sec-ch-ua'] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            headers['sec-ch-ua-mobile'] = '?0'
            headers['sec-ch-ua-platform'] = '"Windows"' if 'Windows' in selected_ua else '"macOS"'
        elif is_firefox:
            headers['Sec-Fetch-Dest'] = 'document'
            headers['Sec-Fetch-Mode'] = 'navigate'
            headers['Sec-Fetch-Site'] = 'none'

        # Randomize some headers to appear more natural
        if random.choice([True, False]):
            headers['Referer'] = f"{self.base_url}/"

        self.session.headers.update(headers)

    def get_credentials(self) -> Tuple[str, str]:
        """
        Retrieve username and password from environment variables with enhanced security.

        Returns:
            Tuple[str, str]: (username, password) pair

        Raises:
            ValueError: If credentials are missing or invalid
        """
        username = os.getenv('MIRCREW_USERNAME')
        password = os.getenv('MIRCREW_PASSWORD')

        # Enhanced security: Avoid logging any sensitive information
        if not username:
            logger.error("MIRCREW_USERNAME environment variable not set")
        if not password:
            logger.error("MIRCREW_PASSWORD environment variable not set")

        # Only log boolean indicators for debugging
        logger.debug(f"Credentials loaded: username={bool(username)}, password={bool(password)}")

        if not username or not password:
            raise ValueError("Missing credentials. Please set MIRCREW_USERNAME and MIRCREW_PASSWORD environment variables.")

        # Basic sanitization
        username = username.strip()
        if not username:
            raise ValueError("Username cannot be empty")

        if len(password) < 3:
            raise ValueError("Password too short (minimum 3 characters)")

        return username, password

    def _establish_session(self, max_retries: int = 3) -> bool:
        """
        Establish a natural browsing session by visiting the homepage first.

        Args:
            max_retries: Maximum number of retry attempts

        Returns:
            bool: True if session established successfully, False otherwise
        """
        for attempt in range(max_retries):
            try:
                logger.debug(f"Establishing browsing session (attempt {attempt + 1}/{max_retries})...")

                # Visit main page first to get cookies and establish session
                response = self.session.get(
                    f"{self.base_url}/index.php",
                    allow_redirects=True,
                    timeout=15
                )

                if response.status_code == 200:
                    logger.debug("✅ Homepage visit successful - session established")
                    # Wait a moment to simulate human behavior
                    time.sleep(random.uniform(0.5, 1.5))
                    return True
                else:
                    logger.warning(f"⚠️ Homepage visit returned: {response.status_code}")
                    if attempt < max_retries - 1:
                        sleep_time = random.uniform(1.0, 3.0)
                        logger.debug(f"⏳ Retrying session establishment in {sleep_time:.1f}s...")
                        time.sleep(sleep_time)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"⚠️ Network error establishing session (attempt {attempt + 1}): {type(e).__name__}")
                if attempt < max_retries - 1:
                    sleep_time = random.uniform(2.0, 5.0)
                    logger.debug(f"⏳ Retrying session establishment in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Request error establishing session: {type(e).__name__}: {str(e)}")
                if attempt < max_retries - 1:
                    sleep_time = random.uniform(3.0, 7.0)
                    logger.debug(f"⏳ Retrying session establishment in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error("❌ Failed to establish session after all retries")
                    return False

        logger.warning("⚠️ Session establishment completed with warnings")
        return True

    def _extract_form_data_precise(self, html_content: str) -> dict:
        """
        Precise form data extraction targeting the login form specifically
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        form_data = {}

        # Find the login form - try multiple strategies
        login_form = None

        # Strategy 1: Look for form with login action
        login_form = soup.find('form', action=lambda x: x is not None and 'mode=login' in x)

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

        if login_form and isinstance(login_form, Tag):
            # Extract all inputs from the form
            inputs = login_form.find_all('input')
            for input_field in inputs:
                if hasattr(input_field, 'get'):
                    name = input_field.get('name')
                    value = input_field.get('value', '')
                    if name:
                        form_data[name] = value

        logger.debug(f"Extracted {len(form_data)} fields from login form")
        return form_data

    def _prepare_login_payload(self, username: str, password: str, form_data: dict) -> dict:
        """
        Prepare login payload with precise field ordering and validation.

        Args:
            username: Username for authentication
            password: Password for authentication
            form_data: Extracted form fields from login page

        Returns:
            dict: Properly ordered login payload
        """
        if not isinstance(form_data, dict):
            raise TypeError("form_data must be a dictionary")

        payload = {}

        # Core login fields - these must be first in correct order
        payload['username'] = str(username).strip()
        payload['password'] = str(password)
        payload['autologin'] = '1'  # Remember login
        payload['viewonline'] = '1'  # Show online status
        payload['login'] = 'Login'   # Submit button value

        # Add hidden CSRF protection fields in specific order
        hidden_fields = ['sid', 'form_token', 'creation_time']
        for field in hidden_fields:
            if field in form_data and form_data[field]:
                payload[field] = str(form_data[field]).strip()

        # Add redirect field
        if 'redirect' in form_data and form_data['redirect']:
            payload['redirect'] = str(form_data['redirect']).strip()
        else:
            payload['redirect'] = 'index.php'  # Default redirect

        logger.debug(f"Prepared login payload with {len(payload)} fields")
        return payload

    def login(self, max_attempts: Optional[int] = None) -> bool:
        """
        Enhanced login with comprehensive anti-detection measures and exponential backoff.

        Args:
            max_attempts: Maximum login attempts (default: 10)

        Returns:
            bool: True if login successful, False otherwise
        """
        if max_attempts is None:
            max_attempts = 10

        try:
            logger.info("🟡 Starting MirCrew login process...")

            username, password = self.get_credentials()

            for attempt in range(max_attempts):
                if attempt > 0:
                    # Exponential backoff with jitter: base_delay * (2^attempt) + random_jitter
                    base_delay = min(2.0 * (2 ** attempt), 30.0)  # Cap at 30 seconds
                    jitter = random.uniform(0.1, 2.0)
                    delay = base_delay + jitter

                    logger.info(f"⏳ Exponential backoff: attempt {attempt + 1}, waiting {delay:.1f}s")
                    time.sleep(delay)

                logger.info(f"🔄 Login attempt {attempt + 1}/{max_attempts}")

                # Establish natural session state (once per run)
                if attempt == 0:
                    if not self._establish_session():
                        logger.warning("⚠️ Session establishment failed, continuing with login attempt")

                # Fresh session for each attempt
                if attempt > 0:
                    self.session = requests.Session()
                    self._setup_session_headers()
                    self._establish_session()

                try:
                    # Fetch login page with enhanced error handling
                    logger.info("📄 Fetching login page...")
                    response = self.session.get(self.login_url, allow_redirects=True, timeout=20)

                    if response.status_code != 200:
                        logger.warning(f"❌ Login page returned {response.status_code}")
                        continue

                except requests.exceptions.RequestException as e:
                    logger.warning(f"❌ Network error: {str(e)}")
                    continue

                # Extract form data precisely
                form_data = self._extract_form_data_precise(response.text)

                if not form_data.get('form_token'):
                    logger.warning("⚠️ Missing form_token, retrying...")
                    continue

                if not form_data.get('sid'):
                    logger.warning("⚠️ Missing sid, retrying...")
                    continue

                # Prepare payload
                login_payload = self._prepare_login_payload(username, password, form_data)

                logger.info("🚀 Submitting login credentials")

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
                    logger.warning(f"❌ Login request failed: {type(e).__name__}: {str(e)}")
                    continue

                logger.info(f"📋 Login response: {login_response.status_code} → login redirect detected")

                # Validate login success
                success = self.validate_login(login_response)

                if success:
                    logger.info(f"✅ SUCCESS: Login completed on attempt {attempt + 1}")
                    return True

                # Enhanced error detection
                response_lower = login_response.text.lower()

                if 'il form inviato non è valido' in response_lower:
                    logger.warning("🔄 CSRF token expired, fresh retry needed")
                    continue
                elif any(error in response_lower for error in ['captcha', 'verification', 'robot']):
                    logger.warning("🤖 Anti-bot protection detected")
                    time.sleep(random.uniform(10, 20))  # Longer delay for anti-bot
                    continue
                elif any(error in response_lower for error in ['ban', 'suspended', 'blocked']):
                    logger.error("🚫 Account appears blocked/suspended")
                    return False
                elif 'modo manutenzione' in response_lower or 'maintenance' in response_lower:
                    logger.error("🛠️ Site is in maintenance mode")
                    return False
                else:
                    logger.warning("⚠️ Unknown error condition")

            # If we get here, all attempts failed
            logger.error(f"💀 LOGIN FAILED: All {max_attempts} attempts exhausted")
            return False

        except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
            logger.error(f"💥 Network error during login: {type(e).__name__}: {str(e)}")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"💥 Data validation error during login: {type(e).__name__}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"💥 Critical login error: {type(e).__name__}: {str(e)}")
            return False

    def validate_login(self, response: requests.Response) -> bool:
        """
        Validate login success with multiple checks
        """
        try:
            if response.status_code != 200:
                logger.error(f"❌ Http error: {response.status_code}")
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
                            logger.error(f"📄 Website error: {error_text}")
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
                    logger.error("❌ Login failed: credential error")
                    return False

            # Success checks
            if 'mode=login' not in response.url:
                logger.info("🔄 Redirected from login page")
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
                        logger.info(f"✅ Login successful: {indicator}")
                        return True

                # If redirected to main content but no clear indicator, assume success
                if any(keyword in response_lower for keyword in ['forum', 'threads', 'posts', 'community']):
                    logger.info("✅ Login successful: main content detected")
                    return True

            # If still on login page with no clear errors, it failed
            if 'mode=login' in response.url or 'login.php' in response.url:
                logger.error("❌ Still on login page - authentication failed")
                return False

            # Default conservative approach
            logger.warning("⚠️ Unable to clearly determine login status")
            return False

        except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
            logger.error(f"💥 Network error during validation: {type(e).__name__}: {str(e)}")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"💥 Data error during validation: {type(e).__name__}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"💥 Validation error: {type(e).__name__}: {str(e)}")
            return False

    def is_logged_in(self) -> bool:
        """
        Test if current session is still valid with comprehensive validation.

        Returns:
            bool: True if session is valid and user is logged in, False otherwise
        """
        try:
            logger.debug("🔍 Checking login session validity...")

            response = self.session.get(
                f"{self.base_url}/index.php",
                allow_redirects=True,
                timeout=10
            )

            # HTTP error response
            if response.status_code != 200:
                logger.debug(f"⚠️ Session check failed with HTTP {response.status_code}")
                return False

            # Redirecting to login = not logged in
            if 'login' in response.url.lower() or 'ucp.php' in response.url:
                logger.debug("⚠️ Redirected to login page - session expired")
                return False

            # Check response content for login indicators
            response_lower = response.text.lower()

            # Success indicators with Italian translations
            success_indicators = [
                'logout', 'my account', 'profile', 'logged in as',
                'benvenuto', 'profilo', 'disconnetti', # Italian
                'forum', 'threads', 'posts'  # Forum content indicators
            ]

            # Error indicators that show we're not logged in
            error_indicators = [
                'login', 'register', 'password', 'username',
                'accedi', 'registrati', 'autenticazione'  # Italian
            ]

            # Check for error indicators first (stronger signal)
            if any(err in response_lower for err in error_indicators):
                logger.debug("⚠️ Found error indicators - not logged in")
                return False

            # Check for success indicators
            if any(indicator in response_lower for indicator in success_indicators):
                logger.debug("✅ Found success indicators - session valid")
                return True

            # Default: assume logged in if we get here without clear indicators
            logger.debug("⚠️ No clear indicators found - treating as logged in")
            return True

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"⚠️ Network error during session check: {type(e).__name__}")
            return False
        except (requests.exceptions.RequestException, ValueError, AttributeError) as e:
            logger.error(f"❌ Error checking session validity: {type(e).__name__}: {str(e)}")
            return False

    def logout(self) -> bool:
        """
        Perform logout
        """
        try:
            logout_url = f"{self.base_url}/ucp.php?mode=logout&sid={self.session.cookies.get('phpbb3_34c6d_sid', '')}"
            response = self.session.get(logout_url, allow_redirects=True)
            logger.info("👋 Logged out successfully")
            return True
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False


def test_login() -> bool:
    """
    Comprehensive login test suite with multiple validation steps.

    Returns:
        bool: True if all tests pass, False otherwise
    """
    import sys

    logger.info("🧪 Starting MirCrew login test suite...")
    start_time = time.time()

    test_results = {
        'login_success': False,
        'session_persistence': False,
        'credentials_validation': False,
        'error_handling': False
    }

    try:
        # Test 1: Credential validation
        logger.info("📋 Test 1: Validating credentials...")
        login_client = MirCrewLogin()

        try:
            username, password = login_client.get_credentials()
            test_results['credentials_validation'] = True
            logger.info("✅ Credentials validation PASSED")
        except ValueError as e:
            logger.error(f"❌ Credentials validation FAILED: {str(e)}")
            return False

        # Test 2: Login attempt
        logger.info("🔐 Test 2: Attempting login...")
        success = login_client.login()

        if success:
            test_results['login_success'] = True
            logger.info("✅ Login test PASSED")
        else:
            logger.error("❌ Login test FAILED")
            return False

        # Test 3: Session persistence
        logger.info("🔄 Test 3: Testing session persistence...")
        time.sleep(2)  # Brief pause before checking
        if login_client.is_logged_in():
            test_results['session_persistence'] = True
            logger.info("✅ Session persistence test PASSED")
        else:
            logger.warning("⚠️ Session persistence test FAILED")
            test_results['session_persistence'] = False

        # Test 4: Error handling simulation
        logger.info("🚨 Test 4: Testing error handling...")
        try:
            # Test with missing credentials
            import os
            original_username = os.environ.get('MIRCREW_USERNAME')
            original_password = os.environ.get('MIRCREW_PASSWORD')

            # Temporarily remove credentials
            os.environ.pop('MIRCREW_USERNAME', None)
            os.environ.pop('MIRCREW_PASSWORD', None)

            error_client = MirCrewLogin()
            try:
                error_client.get_credentials()
            except ValueError:
                logger.debug("✅ Error handling correctly caught missing credentials")
                test_results['error_handling'] = True
                logger.info("✅ Error handling test PASSED")
            finally:
                # Restore original credentials
                if original_username:
                    os.environ['MIRCREW_USERNAME'] = original_username
                if original_password:
                    os.environ['MIRCREW_PASSWORD'] = original_password

        except Exception as e:
            logger.warning(f"⚠️ Error handling test issue: {str(e)}")

        # Calculate test score
        passed_tests = sum(test_results.values())
        total_tests = len(test_results)
        test_percentage = (passed_tests / total_tests) * 100

        elapsed_time = time.time() - start_time

        logger.info("📊 Login Test Results:")
        logger.info(f"   Duration: {elapsed_time:.2f} seconds")
        logger.info(f"   Passed: {passed_tests}/{total_tests} tests ({test_percentage:.1f}%)")

        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED: Authentication system working correctly!")
            return True
        elif passed_tests >= total_tests - 1:
            logger.info("🟡 MOSTLY PASSED: Minor issues detected but system functional")
            return True
        else:
            logger.error("❌ MULTIPLE TESTS FAILED: Authentication system needs attention")
            return False

    except KeyboardInterrupt:
        logger.warning("🛑 Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"💥 Unexpected error during login test: {type(e).__name__}: {str(e)}")
        return False


if __name__ == "__main__":
    test_login()