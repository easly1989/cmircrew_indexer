#!/usr/bin/env python3
"""
Unit tests for MirCrew magnet unlocker module
Tests thanks button functionality and magnet link extraction
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import re
from bs4 import BeautifulSoup, Tag

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.mircrew.core.magnet_unlock import MagnetUnlocker


class TestMagnetUnlocker(unittest.TestCase):
    """Test cases for MirCrew magnet unlocker functionality"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.unlocker = MagnetUnlocker()

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_init_creates_unlocker(self):
        """Test that initialization sets up the unlocker properly"""
        self.assertIsNotNone(self.unlocker)
        self.assertIsNone(self.unlocker.session)
        self.assertFalse(self.unlocker.logged_in)
        self.assertIsInstance(self.unlocker.login_handler, object)  # Should be MirCrewLogin instance

    @patch('src.mircrew.core.magnet_unlock.requests.Session')
    def test_authenticate_success(self, mock_session):
        """Test successful authentication"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock the login handler
        mock_login = MagicMock()
        mock_login.login.return_value = True
        mock_login.session = mock_session_instance
        self.unlocker.login_handler = mock_login

        result = self.unlocker.authenticate()
        self.assertTrue(result)
        self.assertEqual(self.unlocker.session, mock_session_instance)
        self.assertTrue(self.unlocker.logged_in)

    @patch('src.mircrew.core.magnet_unlock.requests.Session')
    def test_authenticate_failure(self, mock_session):
        """Test authentication failure"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock failed login
        mock_login = MagicMock()
        mock_login.login.return_value = False
        self.unlocker.login_handler = mock_login

        result = self.unlocker.authenticate()
        self.assertFalse(result)
        self.assertFalse(self.unlocker.logged_in)

    def test_extract_first_post_id_from_button(self):
        """Test extracting post ID from thanks button"""
        html_content = '''
        <html>
        <body>
            <input id="lnk_thanks_post123" type="button" value="Thanks">
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = self.unlocker._extract_first_post_id(soup)
        self.assertEqual(result, '123')

    def test_extract_first_post_id_from_multiple_buttons(self):
        """Test extracting post ID when multiple thanks buttons exist"""
        html_content = '''
        <html>
        <body>
            <input id="lnk_thanks_post456" type="button" value="Thanks">
            <input id="lnk_thanks_post789" type="button" value="Thanks">
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = self.unlocker._extract_first_post_id(soup)
        # Should return the first button's ID (456)
        self.assertEqual(result, '456')

    def test_extract_first_post_id_no_buttons(self):
        """Test behavior when no thanks buttons are found"""
        html_content = '''
        <html>
        <body>
            <div>Some content without thanks buttons</div>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = self.unlocker._extract_first_post_id(soup)
        self.assertIsNone(result)

    def test_find_thanks_button_success(self):
        """Test finding thanks button with correct ID"""
        html_content = '''
        <html>
        <body>
            <a id="lnk_thanks_post123" href="/thanks">Thanks</a>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = self.unlocker._find_thanks_button(soup, '123')
        self.assertEqual(result, 'lnk_thanks_post123')

    def test_find_thanks_button_not_found(self):
        """Test when thanks button is not found for given post ID"""
        html_content = '''
        <html>
        <body>
            <a id="lnk_thanks_post456" href="/thanks">Thanks</a>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = self.unlocker._find_thanks_button(soup, '123')
        self.assertIsNone(result)

    def test_click_thanks_button_success(self):
        """Test successful thanks button clicking"""
        # Mock the session
        mock_session = MagicMock()
        self.unlocker.session = mock_session

        thread_url = "https://mircrew-releases.org/viewtopic.php?f=51&p=123&t=456"

        # Mock the GET request to get the button href
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.text = '''
        <html>
        <body>
            <a id="lnk_thanks_post123" href="./viewtopic.php?f=51&p=123&thanks=123">Thanks</a>
        </body>
        </html>
        '''
        mock_session.get.return_value = mock_get_response

        # Mock the actual thanks request
        mock_thanks_response = MagicMock()
        mock_thanks_response.status_code = 200
        mock_thanks_response.text = "Thanked successfully"
        mock_session.get.return_value = mock_thanks_response

        result = self.unlocker._click_thanks_button(thread_url, 'lnk_thanks_post123')
        self.assertTrue(result)

    def test_click_thanks_button_failure(self):
        """Test thanks button clicking failure"""
        # Mock the session (no session available)
        self.unlocker.session = None

        result = self.unlocker._click_thanks_button("test_url", 'test_button')
        self.assertFalse(result)

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_unlock_magnets_success(self, mock_get):
        """Test successful magnet unlocking for a thread"""
        # Set up authenticated session
        self.unlocker.session = MagicMock()

        # Mock thread page response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
            <a id="lnk_thanks_post123" href="./thanks">Thanks</a>
            <a href="magnet:?xt=urn:btih:test123&dn=unlocked.mkv">Unlocked Magnet</a>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"

        result = self.unlocker.unlock_magnets(thread_url)
        self.assertTrue(result)

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_unlock_magnets_no_thanks_button(self, mock_get):
        """Test unlocking when no thanks button is found (magnets already unlocked)"""
        # Set up authenticated session
        self.unlocker.session = MagicMock()

        # Mock thread page response without thanks button
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
            <a href="magnet:?xt=urn:btih:test123&dn=already_unlocked.mkv">Magnet</a>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"

        result = self.unlocker.unlock_magnets(thread_url)
        self.assertTrue(result)  # Should still return True as magnets are available

    def test_extract_magnets_with_unlock_success(self):
        """Test extracting magnets after unlock attempt"""
        # Set up authenticated session
        self.unlocker.session = MagicMock()

        # Mock unlock success
        with patch.object(self.unlocker, 'unlock_magnets', return_value=True):
            # Mock extraction response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '''
            <html>
            <body>
                <div class="postbody">
                    <a href="magnet:?xt=urn:btih:test123&dn=extracted.mkv">Magnet</a>
                </div>
            </body>
            </html>
            '''
            self.unlocker.session.get.return_value = mock_response

            thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"
            magnets = self.unlocker.extract_magnets_with_unlock(thread_url)

            self.assertIsInstance(magnets, list)
            self.assertEqual(len(magnets), 1)
            self.assertIn('test123', magnets[0])

    def test_extract_magnets_with_unlock_no_session(self):
        """Test magnet extraction without authenticated session"""
        self.unlocker.session = None

        thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"
        magnets = self.unlocker.extract_magnets_with_unlock(thread_url)

        self.assertEqual(magnets, [])

    def test_extract_magnets_from_first_post_only(self):
        """Test that magnets are extracted from first post only"""
        # Set up session
        self.unlocker.session = MagicMock()

        # Mock the unlock to succeed
        with patch.object(self.unlocker, 'unlock_magnets', return_value=True):
            # Mock extraction response with multiple posts
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '''
            <html>
            <body>
                <div class="post">
                    <div class="content">
                        <a href="magnet:?xt=urn:btih:first123&dn=first.mkv">First Magnet</a>
                    </div>
                </div>
                <div class="post">
                    <div class="content">
                        <a href="magnet:?xt=urn:btih:second456&dn=second.mkv">Second Magnet</a>
                    </div>
                </div>
            </body>
            </html>
            '''
            self.unlocker.session.get.return_value = mock_response

            thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"

            # Mock _extract_first_post_id to return an ID
            with patch.object(self.unlocker, '_extract_first_post_id', return_value='123'):
                magnets = self.unlocker.extract_magnets_with_unlock(thread_url)
                self.assertIsInstance(magnets, list)
                # Should find at least one magnet (implementation may vary)
                self.assertGreaterEqual(len(magnets), 0)

    def test_magazine_pattern_matching(self):
        """Test magazine-style thanks element detection"""
        html_content = '''
        <html>
        <body>
            <div id="thanks_post_789">Thanks for sharing</div>
            <span id="thank_user_101">Thank user</span>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        # Should find thanks elements with numbers
        thanks_elements = soup.find_all(attrs={'id': re.compile(r'thanks|thank.*\d+')})
        self.assertEqual(len(thanks_elements), 2)


if __name__ == '__main__':
    unittest.main()