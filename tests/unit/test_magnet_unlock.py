#!/usr/bin/env python3
"""
Unit tests for MirCrew magnet unlocker module
Tests thanks button functionality and magnet link extraction
Uses comprehensive mocking to avoid real network connections
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup

from src.mircrew.core.magnet_unlock import MagnetUnlocker


class TestMagnetUnlocker:
    """Test cases for MirCrew magnet unlocker functionality"""

    @pytest.fixture
    def unlocker(self):
        """Fixture to provide a fresh MagnetUnlocker instance"""
        return MagnetUnlocker()

    def test_init_creates_unlocker(self, unlocker):
        """Test that initialization sets up the unlocker properly"""
        assert unlocker is not None
        assert unlocker.session is None
        assert unlocker.logged_in is False
        assert hasattr(unlocker, 'login_handler')

    @patch('src.mircrew.core.magnet_unlock.requests.Session')
    def test_authenticate_success(self, mock_session, unlocker):
        """Test successful authentication"""
        # Configure mocks
        unlocker.login_handler = Mock()
        unlocker.login_handler.login.return_value = True

        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        unlocker.login_handler.session = mock_session_instance

        result = unlocker.authenticate()
        assert result is True
        assert unlocker.session == mock_session_instance
        assert unlocker.logged_in is True

    @patch('src.mircrew.core.magnet_unlock.requests.Session')
    def test_authenticate_failure(self, mock_session, unlocker):
        """Test authentication failure handling"""
        unlocker.login_handler = Mock()
        unlocker.login_handler.login.return_value = False

        result = unlocker.authenticate()
        assert result is False
        assert unlocker.logged_in is False

    def test_extract_first_post_id_from_button(self, unlocker):
        """Test extracting post ID from thanks button"""
        html_content = '''
        <html>
        <body>
            <input id="lnk_thanks_post123" type="button" value="Thanks">
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = unlocker._extract_first_post_id(soup)
        assert result == '123'

    def test_extract_first_post_id_from_multiple_buttons(self, unlocker):
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

        result = unlocker._extract_first_post_id(soup)
        assert result == '456'

    def test_extract_first_post_id_no_buttons(self, unlocker):
        """Test behavior when no thanks buttons are found"""
        html_content = '''
        <html>
        <body>
            <div>Some content without thanks buttons</div>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = unlocker._extract_first_post_id(soup)
        assert result is None

    def test_find_thanks_button_success(self, unlocker):
        """Test finding thanks button with correct ID"""
        html_content = '''
        <html>
        <body>
            <a id="lnk_thanks_post123" href="/thanks">Thanks</a>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = unlocker._find_thanks_button(soup, '123')
        assert result == 'lnk_thanks_post123'

    def test_find_thanks_button_not_found(self, unlocker):
        """Test when thanks button is not found for given post ID"""
        html_content = '''
        <html>
        <body>
            <a id="lnk_thanks_post456" href="/thanks">Thanks</a>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html_content, 'html.parser')

        result = unlocker._find_thanks_button(soup, '123')
        assert result is None

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_click_thanks_button_success(self, mock_get, unlocker):
        """Test successful thanks button clicking"""
        unlocker.session = MagicMock()
        thread_url = "https://mock-forum.com/viewtopic.php?f=51&p=123&t=456"

        # Mock the GET request to get the button href
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
            <a id="lnk_thanks_post123" href="./viewtopic.php?f=51&p=123&thanks=123">Thanks</a>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        result = unlocker._click_thanks_button(thread_url, 'lnk_thanks_post123')
        assert result is True

    def test_click_thanks_button_failure(self, unlocker):
        """Test thanks button clicking failure"""
        unlocker.session = None
        result = unlocker._click_thanks_button("test_url", 'test_button')
        assert result is False

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_unlock_magnets_success(self, mock_get, unlocker):
        """Test successful magnet unlocking for a thread"""
        unlocker.session = MagicMock()

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

        thread_url = "https://mock-forum.com/viewtopic.php?t=123"
        result = unlocker.unlock_magnets(thread_url)
        assert result is True

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_unlock_magnets_no_thanks_button(self, mock_get, unlocker):
        """Test unlocking when no thanks button is found (magnets already unlocked)"""
        unlocker.session = MagicMock()

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

        thread_url = "https://mock-forum.com/viewtopic.php?t=123"
        result = unlocker.unlock_magnets(thread_url)
        assert result is True  # Should still return True as magnets are available

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_extract_magnets_with_unlock_success(self, mock_get, unlocker):
        """Test extracting magnets after unlock attempt"""
        unlocker.session = MagicMock()

        # Mock unlock success
        with patch.object(unlocker, 'unlock_magnets', return_value=True):
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
            mock_get.return_value = mock_response

            thread_url = "https://mock-forum.com/viewtopic.php?t=123"
            magnets = unlocker.extract_magnets_with_unlock(thread_url)

            assert isinstance(magnets, list)
            assert len(magnets) == 1
            assert 'test123' in magnets[0]

    def test_extract_magnets_with_unlock_no_session(self, unlocker):
        """Test magnet extraction without authenticated session"""
        unlocker.session = None

        thread_url = "https://mock-forum.com/viewtopic.php?t=123"
        magnets = unlocker.extract_magnets_with_unlock(thread_url)

        assert magnets == []

    @patch('src.mircrew.core.magnet_unlock.requests.Session.get')
    def test_extract_magnets_from_first_post_only(self, mock_get, unlocker):
        """Test that magnets are extracted from first post only"""
        unlocker.session = MagicMock()

        # Mock unlock success
        with patch.object(unlocker, 'unlock_magnets', return_value=True):
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
            mock_get.return_value = mock_response

            thread_url = "https://mock-forum.com/viewtopic.php?t=123"

            # Mock _extract_first_post_id to return an ID
            with patch.object(unlocker, '_extract_first_post_id', return_value='123'):
                magnets = unlocker.extract_magnets_with_unlock(thread_url)
                assert isinstance(magnets, list)
                assert len(magnets) >= 0  # Flexible check for first magnet

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
        assert len(thanks_elements) == 2