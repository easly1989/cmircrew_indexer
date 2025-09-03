"""
Centralized session management with thread safety and lazy authentication.

This module provides a thread-safe way to manage MirCrew forum sessions,
ensuring that authentication is performed only once and reused across
multiple components.
"""
import threading
from typing import Optional

# Set up centralized logging
from .logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
import requests
import time
from ..config.settings import MirCrewConfig


class ThreadSafeSessionManager:
    """Thread-safe manager for MirCrew forum sessions with lazy loading"""

    def __init__(self, config: MirCrewConfig):
        """
        Initialize the session manager.

        Args:
            config: MirCrew configuration instance
        """
        self.config = config
        self._session: Optional[requests.Session] = None
        self._authenticated = False
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._last_check = 0.0
        self._check_interval = 60.0  # Check authentication every 60 seconds

    def get_session(self) -> requests.Session:
        """
        Get authenticated session, creating/authenticating if needed.

        Returns:
            requests.Session: Authenticated session instance

        Raises:
            RuntimeError: If authentication fails or session creation fails
        """
        with self._lock:
            # Check if we need to re-verify authentication
            current_time = time.time()
            if (self._authenticated and
                current_time - self._last_check > self._check_interval):
                self._verified_authentication()

            # Create session if needed
            if not self._session:
                self._create_session()

            # At this point _session is guaranteed to be set (or exception raised)
            assert self._session is not None
            return self._session

    def is_authenticated(self) -> bool:
        """
        Check if current session is authenticated.

        Returns:
            bool: True if session is valid and authenticated
        """
        with self._lock:
            if not self._session or not self._authenticated:
                return False

            # If it's time to verify, do so
            current_time = time.time()
            if current_time - self._last_check > self._check_interval:
                return self._verified_authentication()

            return True

    def invalidate_session(self) -> None:
        """Force session invalidation - useful for error recovery"""
        with self._lock:
            if self._session:
                try:
                    self._session.close()
                except Exception:
                    pass  # Ignore errors when closing

            self._session = None
            self._authenticated = False
            self._last_check = 0.0
            logger.info("Session invalidated")

    def _create_session(self) -> None:
        """Create new session and authenticate it"""
        logger.debug("Creating new session...")

        with self._lock:
            try:
                self._session = requests.Session()
                self._session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7'
                })

                self._authenticated = False
                self._authenticate_session()

            except Exception as e:
                logger.error(f"Failed to create session: {type(e).__name__}: {str(e)}")
                self._session = None
                raise RuntimeError(f"Session creation failed: {str(e)}")

    def _authenticate_session(self) -> None:
        """Authenticate the current session"""
        logger.debug("Authenticating session...")

        with self._lock:
            try:
                from ..core.auth import MirCrewLogin

                auth = MirCrewLogin()
                if auth.login():
                    # Replace our session with the authenticated one
                    if self._session:
                        # Close current session if we created it
                        try:
                            self._session.close()
                        except Exception:
                            pass

                    self._session = auth.session
                    self._authenticated = True
                    self._last_check = time.time()

                    logger.info("✅ Session authentication successful")
                else:
                    self._authenticated = False
                    raise RuntimeError("Authentication failed - check credentials")

            except Exception as e:
                logger.error(f"Session authentication error: {type(e).__name__}: {str(e)}")
                self._authenticated = False
                raise

    def _verified_authentication(self) -> bool:
        """Verify current session is still authenticated"""
        with self._lock:
            if not self._session or not self._authenticated:
                return False

            try:
                logger.debug("Verifying session authentication...")
                from ..core.auth import MirCrewLogin

                # Create a temporary auth instance to check without full login
                auth = MirCrewLogin()
                # We could implement a lighter check here without credentials

                # For now, we assume authentication is still valid
                # In a more advanced implementation, we could check a protected page
                self._last_check = time.time()
                return True

            except Exception as e:
                logger.warning(f"Session verification failed: {type(e).__name__}: {str(e)}")
                self._authenticated = False
                return False


# Backwards compatibility alias
SessionManager = ThreadSafeSessionManager


def get_shared_session_manager(config: MirCrewConfig) -> ThreadSafeSessionManager:
    """
    Factory function to create a configured session manager.

    Args:
        config: MirCrew configuration instance

    Returns:
        ThreadSafeSessionManager: Configured session manager instance
    """
    return ThreadSafeSessionManager(config)