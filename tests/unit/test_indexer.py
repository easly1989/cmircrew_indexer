#!/usr/bin/env python3
"""
Unit tests for MirCrew indexer module
Tests Torznab API functionality, XML generation, and search operations
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
from datetime import datetime
from urllib.parse import urljoin

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.mircrew.core.indexer import MirCrewIndexer


class TestMirCrewIndexer(unittest.TestCase):
    """Test cases for MirCrew indexer functionality"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.indexer = MirCrewIndexer()

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_init_sets_up_categories(self):
        """Test that initialization sets up category mappings correctly"""
        self.assertIsNotNone(self.indexer.cat_mappings)
        self.assertEqual(self.indexer.cat_mappings['25'], 'Movies')
        self.assertEqual(self.indexer.cat_mappings['51'], 'TV')

    def test_init_sets_up_default_sizes(self):
        """Test that initialization sets up default sizes correctly"""
        self.assertEqual(self.indexer.default_sizes['Movies'], '10GB')
        self.assertEqual(self.indexer.default_sizes['TV'], '2GB')

    def test_base_url_correct(self):
        """Test that base URL is properly set"""
        self.assertEqual(self.indexer.base_url, "https://mircrew-releases.org")

    @patch('src.mircrew.core.indexer.requests.Session')
    def test_authenticate_success(self, mock_session):
        """Test successful authentication"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock the login handler
        mock_login = MagicMock()
        mock_login.login.return_value = True
        mock_login.session = mock_session_instance
        self.indexer.login_handler = mock_login

        result = self.indexer.authenticate()
        self.assertTrue(result)
        self.assertEqual(self.indexer.session, mock_session_instance)
        self.assertTrue(self.indexer.logged_in)

    @patch('src.mircrew.core.indexer.requests.Session')
    def test_authenticate_failure(self, mock_session):
        """Test authentication failure"""
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance

        # Mock failed login
        mock_login = MagicMock()
        mock_login.login.return_value = False
        self.indexer.login_handler = mock_login

        result = self.indexer.authenticate()
        self.assertFalse(result)
        self.assertFalse(self.indexer.logged_in)

    def test_build_search_query_basic(self):
        """Test basic search query building"""
        result = self.indexer.build_search_query("test query")
        self.assertEqual(result, '"test query"')

    def test_build_search_query_with_season_ep(self):
        """Test search query building with season and episode"""
        result = self.indexer.build_search_query("Show Name", "01", "05")
        self.assertEqual(result, '"Show Name" S01E05')

    def test_build_search_query_season_only(self):
        """Test search query building with season only"""
        result = self.indexer.build_search_query("Show Name", "02")
        self.assertEqual(result, '"Show Name" S02')

    def test_prepare_search_keywords(self):
        """Test search keyword preparation"""
        result = self.indexer.prepare_search_params("test query")
        self.assertEqual(result, ['+test', '+query'])

    def test_prepare_search_keywords_single_word(self):
        """Test search keyword preparation with single word"""
        result = self.indexer.prepare_search_params("single")
        self.assertEqual(result, ['+single'])

    def test_search_thread_by_id_direct(self):
        """Test direct thread search by ID"""
        thread_id = "123456"
        query = f"thread::{thread_id}"

        with patch.object(self.indexer, 'authenticate', return_value=True):
            with patch.object(self.indexer, '_extract_thread_magnets', return_value=[
                {
                    'title': 'Thread Magnet',
                    'link': 'magnet:?xt=urn:btih:test123&dn=file.mkv',
                    'details': 'https://mircrew-releases.org/viewtopic.php?t=123456',
                    'category_id': '25'
                }
            ]):
                result = self.indexer._search_thread_by_id(query)

                # Should contain XML structure
                self.assertIn('<?xml version="1.0"', result)
                self.assertIn('<rss version="2.0"', result)
                self.assertIn('thread-123456-0', result)

    def test_search_thread_by_id_invalid(self):
        """Test direct thread search with invalid ID format"""
        query = "thread::invalid"
        result = self.indexer._search_thread_by_id(query)

        # Should return error response
        self.assertIn('<error', result)

    def test_contains_partial_match_direct(self):
        """Test partial matching functionality"""
        # Test exact match
        result = self.indexer._contains_partial_match("test", "test movie")
        self.assertTrue(result)

        # Test no match
        result = self.indexer._contains_partial_match("xyz", "test movie")
        self.assertFalse(result)

    def test_contains_partial_match_hyphenated(self):
        """Test partial matching with hyphenated words"""
        result = self.indexer._contains_partial_match("blue", "Blu-ray")
        self.assertTrue(result)

    def test_contains_partial_match_colon(self):
        """Test partial matching with colon-separated terms"""
        result = self.indexer._contains_partial_match("test", "Test: Movie")
        self.assertTrue(result)

    def test_filter_relevant_results(self):
        """Test filtering threads based on search relevance"""
        threads = [
            {'title': 'The Matrix Movie', 'full_text': 'action sci-fi'},
            {'title': 'Random Movie', 'full_text': 'drama'},
            {'title': 'Unrelated', 'full_text': 'documentary'}
        ]

        original_query = "matrix"
        result = self.indexer._filter_relevant_results(threads, original_query)

        # Should find the relevant thread
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'The Matrix Movie')

    def test_parse_search_results_success(self):
        """Test parsing search results HTML"""
        html_content = '''
        <html>
        <body>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=123">Test Thread</a>
                <time datetime="2023-12-01T12:00:00"></time>
            </li>
        </body>
        </html>
        '''

        keywords = "test"
        result = self.indexer._parse_search_results(html_content, keywords)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Test Thread')
        self.assertEqual(result[0]['category'], 'Movies')  # Default for non-season content
        self.assertEqual(result[0]['category_id'], '25')

    def test_parse_search_results_tv_content(self):
        """Test parsing search results for TV content"""
        html_content = '''
        <html>
        <body>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=123">Dexter S01</a>
                <time datetime="2023-12-01T12:00:00"></time>
            </li>
        </body>
        </html>
        '''

        keywords = "dexter s01"
        result = self.indexer._parse_search_results(html_content, keywords)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'TV')  # Should detect TV content
        self.assertEqual(result[0]['category_id'], '52')

    def test_parse_search_results_empty(self):
        """Test parsing empty search results"""
        html_content = '''
        <html>
        <body>
            <div>No results found</div>
        </body>
        </html>
        '''

        result = self.indexer._parse_search_results(html_content, "test")
        self.assertEqual(len(result), 0)

    @patch('src.mircrew.core.indexer.requests.Session.get')
    def test_extract_thread_magnets_success(self, mock_get):
        """Test successful magnet extraction from thread"""
        # Set up session
        self.indexer.session = MagicMock()
        self.indexer.unlocker = MagicMock()

        thread_info = {
            'title': 'Test Thread',
            'details': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'category_id': '25'
        }

        # Mock unlocker to return magnets
        self.indexer.unlocker.extract_magnets_with_unlock.return_value = [
            'magnet:?xt=urn:btih:test123&dn=test.mkv'
        ]

        result = self.indexer._extract_thread_magnets(thread_info)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'test.mkv')  # Should use filename
        self.assertIn('test123', result[0]['link'])

    @patch('src.mircrew.core.indexer.requests.Session.get')
    def test_extract_thread_magnets_fallback(self, mock_get):
        """Test magnet extraction fallback when display name is not found"""
        # Set up session
        self.indexer.session = MagicMock()
        self.indexer.unlocker = MagicMock()

        thread_info = {
            'title': 'Test Thread',
            'details': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'category_id': '25'
        }

        # Mock unlocker to return magnets without display name
        self.indexer.unlocker.extract_magnets_with_unlock.return_value = [
            'magnet:?xt=urn:btih:test123'  # No display name
        ]

        result = self.indexer._extract_thread_magnets(thread_info)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Test Thread')  # Should use thread title as fallback

    def test_build_torznab_xml_structure(self):
        """Test basic Torznab XML structure generation"""
        magnets = [
            {
                'title': 'Test Magnet',
                'link': 'magnet:?xt=urn:btih:test123&dn=test.mkv',
                'details': 'https://mircrew-releases.org/viewtopic.php?t=123',
                'category_id': '25',
                'size': '1073741824',  # 1GB
                'pub_date': '2023-12-01T12:00:00',
                'seeders': 1,
                'peers': 2
            }
        ]

        result = self.indexer._build_torznab_xml(magnets)

        # Check XML structure
        self.assertIn('<?xml version="1.0"', result)
        self.assertIn('<rss version="2.0"', result)
        self.assertIn('<channel>', result)
        self.assertIn('<item>', result)
        self.assertIn('<title>Test Magnet</title>', result)
        self.assertIn('<guid>', result)
        self.assertIn('<link>', result)
        self.assertIn('<enclosure', result)
        self.assertIn('test123', result)

    def test_extract_display_name_success(self):
        """Test successful display name extraction from magnet URL"""
        magnet_url = 'magnet:?xt=urn:btih:test123&dn=Sample.Movie.1080p.BluRay.x264.mkv'

        result = self.indexer._extract_display_name(magnet_url)
        self.assertEqual(result, 'Sample.Movie.1080p.BluRay.x264.mkv')

    def test_extract_display_name_no_dn_parameter(self):
        """Test display name extraction when dn parameter is missing"""
        magnet_url = 'magnet:?xt=urn:btih:test123'  # No dn parameter

        result = self.indexer._extract_display_name(magnet_url)
        self.assertIsNone(result)

    def test_extract_display_name_invalid_url(self):
        """Test display name extraction with invalid magnet URL"""
        magnet_url = 'https://example.com'  # Not a magnet URL

        result = self.indexer._extract_display_name(magnet_url)
        self.assertIsNone(result)

    def test_extract_magnet_hash_success(self):
        """Test successful magnet hash extraction"""
        magnet_url = 'magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef'

        result = self.indexer._extract_magnet_hash(magnet_url)
        self.assertEqual(result, 'abcdef1234567890abcdef1234567890abcdef')

    def test_extract_magnet_hash_invalid_format(self):
        """Test magnet hash extraction with invalid format"""
        magnet_url = 'magnet:?xt=urn:btih:short'  # Hash too short

        result = self.indexer._extract_magnet_hash(magnet_url)
        self.assertEqual(result, '')  # Should return empty string for invalid hash

    def test_convert_size_to_bytes_gb(self):
        """Test size conversion to bytes for GB values"""
        result = self.indexer._convert_size_to_bytes('2GB')
        self.assertEqual(result, 2000000000)  # 2 * 1000^3

    def test_convert_size_to_bytes_mb(self):
        """Test size conversion to bytes for MB values"""
        result = self.indexer._convert_size_to_bytes('512MB')
        self.assertEqual(result, 512000000)  # 512 * 1000^2

    def test_convert_size_to_bytes_invalid(self):
        """Test size conversion with invalid format"""
        result = self.indexer._convert_size_to_bytes('invalid')
        self.assertGreater(result, 0)  # Should return default value

    def test_escape_xml_special_chars(self):
        """Test XML escaping of special characters"""
        text = '''Title & "Name" <with> 'special' chars'''
        expected = '''Title & "Name" <with> 'special' chars'''

        result = self.indexer._escape_xml(text)
        self.assertEqual(result, expected)

    def test_error_response_structure(self):
        """Test error response XML structure"""
        message = "Test error message"
        result = self.indexer._error_response(message)

        self.assertIn('<?xml version="1.0"', result)
        self.assertIn('<rss version="2.0">', result)
        self.assertIn('<error', result)
        self.assertIn('Test error message', result)

    def test_thread_search_constructs_correct_url(self):
        """Test that thread search constructs correct URLs"""
        # This test ensures the URL patterns are correct
        thread_id = "180404"
        expected_url = f"{self.indexer.base_url}/viewtopic.php?t={thread_id}"

        # Verify URL construction logic
        self.assertEqual(expected_url, "https://mircrew-releases.org/viewtopic.php?t=180404")


if __name__ == '__main__':
    unittest.main()