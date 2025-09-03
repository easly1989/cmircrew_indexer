#!/usr/bin/env python3
"""
Unit tests for MirCrew authentication module
Tests login functionality, session management, and credential validation
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
from typing import Tuple

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.mircrew.core.auth import MirCrewLogin


class TestMirCrewLogin(unittest.TestCase):
    """Test cases for MirCrew login functionality"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.login_client = MirCrewLogin()

        # Mock environment variables for testing
        self.mock_env = {
            'MIRCREW_USERNAME': 'testuser',
            'MIRCREW_PASSWORD': 'testpass'
        }

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_init_creates_session(self):
        """Test that initialization creates a requests Session"""
        self.assertIsNotNone(self.login_client.session)
        self.assertIsNotNone(self.login_client.base_url)

    def test_get_credentials_success(self):
        """Test credential retrieval from environment variables"""
        with patch.dict(os.environ, self.mock_env):
            username, password = self.login_client.get_credentials()
            self.assertEqual(username, 'testuser')
            self.assertEqual(password, 'testpass')

    def test_get_credentials_missing_username(self):
        """Test credential retrieval fails when username is missing"""
        with patch.dict(os.environ, {'MIRCREW_PASSWORD': 'testpass'}):
            with self.assertRaises(ValueError) as context:
                self.login_client.get_credentials()
            self.assertIn("Missing credentials", str(context.exception))

    def test_get_credentials_missing_password(self):
        """Test credential retrieval fails when password is missing"""
        with patch.dict(os.environ, {'MIRCREW_USERNAME': 'testuser'}):
            with self.assertRaises(ValueError) as context:
                self.login_client.get_credentials()
            self.assertIn("Missing credentials", str(context.exception))

    @patch('mircrew.core.auth.requests.Session')
    def test_setup_session_headers(self, mock_session):
        """Test session headers are properly configured"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Create new client to trigger setup
        client = MirCrewLogin()

        # Verify headers were updated
        mock_session_instance.headers.update.assert_called_once()
        call_args = mock_session_instance.headers.update.call_args[0][0]

        # Check for essential headers
        self.assertIn('User-Agent', call_args)
        self.assertIn('Accept', call_args)
        self.assertIn('Accept-Language', call_args)
        self.assertIn('DNT', call_args)

    @patch('mircrew.core.auth.MirCrewLogin.get_credentials')
    @patch('mircrew.core.auth.requests.Session.get')
    @patch('mircrew.core.auth.requests.Session.post')
    def test_login_flow_success(self, mock_post, mock_get, mock_credentials):
        """Test successful login flow"""
        mock_credentials.return_value = ('testuser', 'testpass')

        # Mock homepage visit
        mock_homepage_response = MagicMock()
        mock_homepage_response.status_code = 200
        mock_get.return_value = mock_homepage_response

        # Mock login page response
        mock_login_page_response = MagicMock()
        mock_login_page_response.status_code = 200
        mock_login_page_response.text = '''
        <form action="ucp.php?mode=login">
            <input name="username" value="">
            <input name="password" value="">
            <input name="form_token" value="test_token">
            <input name="sid" value="test_sid">
        </form>
        '''
        mock_get.return_value = mock_login_page_response

        # Mock login POST response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_login_response.text = '<title>Welcome</title>'
        mock_login_response.url = 'https://mircrew-releases.org/index.php'
        mock_post.return_value = mock_login_response

        with patch.dict(os.environ, self.mock_env):
            success = self.login_client.login()
            self.assertTrue(success)

    @patch('mircrew.core.auth.requests.Session.get')
    def test_login_network_error(self, mock_get):
        """Test login handles network errors gracefully"""
        mock_get.side_effect = ConnectionError("Network error")

        with patch.dict(os.environ, self.mock_env):
            success = self.login_client.login()
            self.assertFalse(success)

    def test_validate_login_success(self):
        """Test successful login validation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = 'https://mircrew-releases.org/index.php'
        mock_response.text = '''
        <html>
        <head><title>Logged in - Welcome</title></head>
        <body>
        <a href="/logout">Logout</a>
        <a href="/profile">My Account</a>
        </body>
        </html>
        '''

        success = self.login_client.validate_login(mock_response)
        self.assertTrue(success)

    def test_validate_login_failure(self):
        """Test failed login validation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = 'https://mircrew-releases.org/ucp.php?mode=login'
        mock_response.text = '''
        <html>
        <head><title>Login</title></head>
        <body>
        <div class="error">Login unsuccessful</div>
        </body>
        </html>
        '''

        success = self.login_client.validate_login(mock_response)
        self.assertFalse(success)

    @patch('mircrew.core.auth.requests.Session.get')
    def test_is_logged_in_true(self, mock_get):
        """Test logged in status check returns True"""
        mock_response = MagicMock()
        mock_response.url = 'https://mircrew-releases.org/index.php'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.login_client.is_logged_in()
        self.assertTrue(result)

    @patch('mircrew.core.auth.requests.Session.get')
    def test_is_logged_in_false(self, mock_get):
        """Test logged in status check returns False when redirected to login"""
        mock_response = MagicMock()
        mock_response.url = 'https://mircrew-releases.org/ucp.php?mode=login'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.login_client.is_logged_in()
        self.assertFalse(result)

    @patch('mircrew.core.auth.requests.Session.get')
    def test_logout_success(self, mock_get):
        """Test successful logout"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.login_client.logout()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()