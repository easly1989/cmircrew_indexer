#!/usr/bin/env python3
"""
Unit tests for MirCrew scraper module
Tests web scraping functionality, HTML parsing, and magnet link extraction
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
from bs4 import BeautifulSoup

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from urllib.parse import urljoin
from src.mircrew.core.scraper import MirCrewScraper


class TestMirCrewScraper(unittest.TestCase):
    """Test cases for MirCrew scraper functionality"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.scraper = MirCrewScraper()

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_init_creates_session(self):
        """Test that initialization creates a requests Session with proper headers"""
        self.assertIsNotNone(self.scraper.session)
        self.assertIn('User-Agent', self.scraper.session.headers)
        self.assertIn('Accept', self.scraper.session.headers)

    def test_base_url_correct(self):
        """Test that base URL is properly set"""
        self.assertEqual(self.scraper.base_url, "https://mircrew-releases.org")

    @patch('src.mircrew.core.scraper.requests.Session.get')
    def test_authenticate_success(self, mock_get):
        """Test successful authentication flow"""
        # Mock homepage response
        mock_homepage = MagicMock()
        mock_homepage.status_code = 200
        mock_get.return_value = mock_homepage

        # Mock the MirCrewLogin class
        with patch('src.mircrew.core.scraper.MirCrewLogin') as mock_login_class:
            mock_login_instance = MagicMock()
            mock_login_instance.login.return_value = True
            mock_login_instance.session = MagicMock()
            mock_login_class.return_value = mock_login_instance

            print_capture = []
            with patch('builtins.print', side_effect=lambda x: print_capture.append(x)):
                result = self.scraper.authenticate()

                # Verify login was attempted
                mock_login_class.assert_called_once()
                mock_login_instance.login.assert_called_once()

                # Check output
                self.assertIn("🔐 Authenticating...", print_capture)
                self.assertIn("✅ Authentication successful", print_capture)

    @patch('src.mircrew.core.scraper.requests.Session.get')
    def test_authenticate_failure(self, mock_get):
        """Test authentication failure"""
        # Mock homepage response
        mock_homepage = MagicMock()
        mock_homepage.status_code = 200
        mock_get.return_value = mock_homepage

        # Mock failed login
        with patch('src.mircrew.core.scraper.MirCrewLogin') as mock_login_class:
            mock_login_instance = MagicMock()
            mock_login_instance.login.return_value = False
            mock_login_class.return_value = mock_login_instance

            print_capture = []
            with patch('builtins.print', side_effect=lambda x: print_capture.append(x)):
                with self.assertRaises(RuntimeError) as context:
                    self.scraper.authenticate()

                self.assertIn("Authentication failed", str(context.exception))
                self.assertIn("🔐 Authenticating...", print_capture)

    def test_parse_search_page_with_results(self):
        """Test parsing search page HTML with results"""
        html_content = '''
        <html>
        <body>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=123">Test Movie Thread</a>
                <time datetime="2023-12-01T12:00:00"></time>
            </li>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=456">Another Movie</a>
            </li>
        </body>
        </html>
        '''

        threads = self.scraper._parse_search_page(html_content)

        self.assertEqual(len(threads), 2)
        self.assertEqual(threads[0]['title'], 'Test Movie Thread')
        self.assertIn('viewtopic.php?t=123', threads[0]['url'])
        self.assertEqual(threads[0]['date'], '2023-12-01T12:00:00')

    def test_parse_search_page_empty(self):
        """Test parsing search page with no results"""
        html_content = '''
        <html>
        <body>
            <div>No results found</div>
        </body>
        </html>
        '''

        threads = self.scraper._parse_search_page(html_content)
        self.assertEqual(len(threads), 0)

    @patch('src.mircrew.core.scraper.requests.Session.get')
    def test_extract_thread_magnets_success(self, mock_get):
        """Test successful magnet extraction from thread"""
        # Mock thread page response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
        <body>
            <a href="magnet:?xt=urn:btih:testmagnet123&dn=Test.File.mkv">Download</a>
            <a href="magnet:?xt=urn:btih:testmagnet456&dn=Another.File.avi">Download 2</a>
        </body>
        </html>
        '''
        mock_get.return_value = mock_response

        thread_info = {
            'title': 'Test Thread',
            'url': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'id': '123',
            'category': 'Movies'
        }

        magnets = self.scraper._extract_thread_magnets(thread_info)

        # Should find both magnets
        self.assertEqual(len(magnets), 2)
        self.assertIn('testmagnet123', magnets[0]['magnet_url'])
        self.assertIn('testmagnet456', magnets[1]['magnet_url'])
        self.assertEqual(magnets[0]['thread_title'], 'Test Thread')

    @patch('src.mircrew.core.scraper.requests.Session.get')
    def test_extract_thread_magnets_failure(self, mock_get):
        """Test magnet extraction when request fails"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        thread_info = {
            'title': 'Test Thread',
            'url': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'id': '123',
            'category': 'Movies'
        }

        magnets = self.scraper._extract_thread_magnets(thread_info)
        # Should return empty list on failure
        self.assertEqual(len(magnets), 0)

    def test_extract_thread_magnets_with_text_magnets(self):
        """Test extracting magnets that are in plain text content"""
        html_content = '''
        <html>
        <body>
            <div class="content">
                Copy this magnet link: magnet:?xt=urn:btih:textmagnet123&dn=Plain.Text.File.mkv
            </div>
            <code>
                magnet:?xt=urn:btih:codemagnet456&dn=Code.File.avi
            </code>
        </body>
        </html>
        '''

        # Create a thread info dict
        thread_info = {
            'title': 'Test Thread',
            'url': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'id': '123',
            'category': 'Movies'
        }

        # Mock the session.get to return our HTML
        with patch('src.mircrew.core.scraper.requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = html_content
            mock_get.return_value = mock_response

            magnets = self.scraper._extract_thread_magnets(thread_info)
            # Should find magnets in both text and code elements
            self.assertTrue(len(magnets) >= 1)

    def test_process_magnet_url_cleaning(self):
        """Test magnet URL processing and cleaning"""
        magnet_url = "magnet:?xt=urn:btih:test123&dn=Test.File.mkv#fragment"
        thread_info = {'title': 'Test'}
        magnets = []
        found_magnets = set()

        self.scraper._process_magnet_url(magnet_url, thread_info, magnets, found_magnets)

        self.assertEqual(len(magnets), 1)
        self.assertEqual(magnets[0]['magnet_url'], "magnet:?xt=urn:btih:test123&dn=Test.File.mkv")
        self.assertNotIn('#fragment', magnets[0]['magnet_url'])

    def test_format_results(self):
        """Test formatting of scraper results"""
        magnets = [
            {
                'thread_title': 'Thread One',
                'magnet_url': 'magnet:?xt=urn:btih:test123&dn=File.One.mkv',
                'thread_id': '123',
                'category': 'Movies'
            },
            {
                'thread_title': 'Thread Two',
                'magnet_url': 'magnet:?xt=urn:btih:test456&dn=File.Two.avi',
                'thread_id': '456',
                'category': 'TV'
            }
        ]

        result = self.scraper._format_results(magnets)

        # Check basic structure
        self.assertIn("MIRCrew Forum Scraper Results", result)
        self.assertIn("Total magnet links found: 2", result)
        self.assertIn("File.One.mkv", result)
        self.assertIn("File.Two.avi", result)
        self.assertIn("="*80, result)

    @patch('src.mircrew.core.scraper.requests.Session.get')
    def test_search_forum_with_auth(self, mock_get):
        """Test full search forum workflow with authentication"""
        # Mock the authentication
        with patch.object(self.scraper, 'authenticate') as mock_auth:
            mock_auth.return_value = None  # authenticate returns None on success

            # Mock search response
            mock_search_response = MagicMock()
            mock_search_response.status_code = 200
            mock_search_response.text = '''
            <html><body>
                <li class="row">
                    <a class="topictitle" href="viewtopic.php?t=123">Test Thread</a>
                </li>
            </body></html>
            '''
            mock_get.return_value = mock_search_response

            # Mock thread extraction
            with patch.object(self.scraper, '_extract_thread_magnets', return_value=[
                {
                    'thread_title': 'Test Thread',
                    'magnet_url': 'magnet:?xt=urn:btih:test123&dn=Test.File.mkv',
                    'category': 'Movies'
                }
            ]):
                print_capture = []
                with patch('builtins.print', side_effect=lambda x: print_capture.append(x)):
                    result = self.scraper.search_forum("test query")

                    # Verify output structure
                    self.assertIn("🔍 Searching for: 'test query'", print_capture)
                    self.assertIn("🎯 Found 1 threads", print_capture)
                    self.assertIn("🎉 Total results: 1", print_capture)
                    self.assertIsInstance(result, str)

if __name__ == '__main__':
    unittest.main()