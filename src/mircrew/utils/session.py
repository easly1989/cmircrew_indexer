"""Centralized session management"""
from typing import Optional

# Set up centralized logging
from .logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)
import requests
from ..config.settings import MirCrewConfig

logger = get_logger(__name__)

class SessionManager:
    """Manages authentication and session state across components"""

    def __init__(self, config: MirCrewConfig):
        self.config = config
        self.session: Optional[requests.Session] = None
        self.authenticated = False

    def get_session(self) -> requests.Session:
        """Get authenticated session, creating if needed"""
        if not self.session or not self.authenticated:
            self._create_session()
        return self.session

    def _create_session(self):
        """Create and authenticate session"""
        from ..core.auth import MirCrewLogin

        auth = MirCrewLogin()
        if auth.login():
            self.session = auth.session
            self.authenticated = True
            logger.info("Session authenticated successfully")
        else:
            raise Exception("Failed to authenticate session")