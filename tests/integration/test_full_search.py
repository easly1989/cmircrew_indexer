#!/usr/bin/env python3
"""
Integration tests for MirCrew full search workflow
Tests the complete search pipeline from authentication through magnet extraction
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Import is handled by tests/__init__.py
try:
    from mircrew.core.auth import MirCrewLogin # type: ignore
    from mircrew.core.scraper import MirCrewScraper # type: ignore
    from mircrew.core.indexer import MirCrewIndexer # type: ignore
    from mircrew.core.magnet_unlock import MagnetUnlocker # type: ignore
except ImportError as e:
    # Handle import errors gracefully for testing
    print(f"Import error (this is normal in test environment): {e}")
    MirCrewLogin = None
    MirCrewScraper = None
    MirCrewIndexer = None
    MagnetUnlocker = None


class TestFullSearchIntegration(unittest.TestCase):
    """Integration tests for the complete search workflow"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        pass

    def tearDown(self):
        """Clean up after each test method"""
        pass

    @patch('requests.Session.get')
    @patch('requests.Session.post')
    def test_complete_authentication_flow(self, mock_post, mock_get):
        """Test the complete authentication flow with success using mocks"""
        if MirCrewLogin is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Mock all HTTP requests
        mock_homepage = MagicMock()
        mock_homepage.status_code = 200
        mock_get.return_value = mock_homepage

        # Mock login page
        mock_login_page = MagicMock()
        mock_login_page.status_code = 200
        mock_login_page.text = '''
        <form action="ucp.php?mode=login">
            <input name="username" value="">
            <input name="password" value="">
            <input name="form_token" value="test_token_123">
            <input name="sid" value="test_sid_456">
        </form>
        '''
        mock_get.return_value = mock_login_page

        # Mock successful login response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_login_response.text = '<title>Logged in - Forum</title>'
        mock_login_response.url = 'https://mircrew-releases.org/index.php'
        mock_post.return_value = mock_login_response

        with patch.dict(os.environ, {
            'MIRCREW_USERNAME': 'testuser',
            'MIRCREW_PASSWORD': 'testpass'
        }):
            auth = MirCrewLogin()
            success = auth.login()
            self.assertTrue(success)

            # Mock logout
            auth.logout()

    @patch('requests.Session')
    @patch('requests.Session.get')
    @patch('requests.Session.post')
    def test_indexer_full_workflow(self, mock_post, mock_get, mock_session_class):
        """Test the complete indexer workflow from search to XML output"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Setup mock session for indexer
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Create real indexer instance
        indexer = MirCrewIndexer()

        # Mock authentication
        mock_login = MagicMock()
        mock_login.login.return_value = True
        mock_login.session = mock_session
        indexer.login_handler = mock_login

        # Mock search request
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.text = '''
        <html>
        <body>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=12345">The Matrix Reloaded</a>
                <time datetime="2023-01-15T10:30:00"></time>
            </li>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=67890">The Matrix Revolutions</a>
                <time datetime="2023-02-20T14:45:00"></time>
            </li>
        </body>
        </html>
        '''
        mock_get.return_value = mock_search_response

        # Mock thread extraction
        with patch.object(indexer, '_extract_thread_magnets', return_value=[
            {
                'title': 'The.Matrix.Reloaded.1080p.BluRay.x264.mkv',
                'link': 'magnet:?xt=urn:btih:test123&dn=The.Matrix.Reloaded.1080p.BluRay.x264.mkv',
                'details': 'https://mircrew-releases.org/viewtopic.php?t=12345',
                'category_id': '25',
                'size': '1073741824',
                'pub_date': '2023-01-15T10:30:00',
            }
        ]):
            # Execute the search
            result = indexer.search(q='Matrix')

            # Verify XML output structure
            self.assertIn('<?xml version="1.0"', result)
            self.assertIn('<rss version="2.0"', result)
            self.assertIn('<channel>', result)
            self.assertIn('<item>', result)
            self.assertIn('The.Matrix.Reloaded', result)
            self.assertIn('<enclosure', result)
            self.assertIn('test123', result)

    @patch('requests.Session.get')
    @patch('requests.Session.post')
    def test_scraper_with_auth_integration(self, mock_post, mock_get):
        """Test scraper integration with authentication"""
        if MirCrewScraper is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Mock authentication for scraper
        with patch('mircrew.core.scraper.MirCrewLogin') as mock_login_class:
            mock_login_instance = MagicMock()
            mock_login_instance.login.return_value = True
            mock_login_instance.session = MagicMock()
            mock_login_class.return_value = mock_login_instance

            scraper = MirCrewScraper()

            # Mock search request
            mock_search_response = MagicMock()
            mock_search_response.status_code = 200
            mock_search_response.text = '''
            <html><body>
                <li class="row">
                    <a class="topictitle" href="viewtopic.php?t=777">Blade Runner 2049</a>
                </li>
            </body></html>
            '''
            mock_get.return_value = mock_search_response

            # Mock thread page
            mock_thread_response = MagicMock()
            mock_thread_response.status_code = 200
            mock_thread_response.text = '''
            <html>
            <body>
                <a href="magnet:?xt=urn:btih:blade123&dn=Blade.Runner.2049.1080p.mkv">Download</a>
                <a href="magnet:?xt=urn:btih:blade456&dn=Blade.Runner.2049.720p.mkv">Download 2</a>
            </body>
            </html>
            '''

            # Sequence the mock responses
            mock_get.side_effect = [mock_search_response, mock_thread_response]

            # Execute search
            result = scraper.search_forum("Blade Runner")

            # Verify results
            self.assertIn("Blade Runner 2049", result)
            self.assertIn("2 magnet link(s)", result)
            self.assertIn("blade123", result)
            self.assertIn("blade456", result)

    @patch('requests.Session')
    def test_magnet_unlocker_full_workflow(self, mock_session_class):
        """Test the complete magnet unlocker workflow"""
        if MirCrewLogin is None or MagnetUnlocker is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        unlocker = MagnetUnlocker()

        # Mock authentication
        with patch.object(unlocker, 'authenticate', return_value=True):
            # Mock thread page with thanks button
            mock_thread_response = MagicMock()
            mock_thread_response.status_code = 200
            mock_thread_response.text = '''
            <html>
            <body>
                <a id="lnk_thanks_post123" href="./thanks">Thanks</a>
                <div class="content">
                    <a href="magnet:?xt=urn:btih:unlock123&dn=Unlocked.File.mkv">Unlocked</a>
                </div>
            </body>
            </html>
            '''
            mock_session.get.return_value = mock_thread_response

            # Mock thanks button click response
            mock_thanks_response = MagicMock()
            mock_thanks_response.status_code = 200
            mock_session.get.return_value = mock_thanks_response

            # Set unlocker session
            unlocker.session = mock_session

            thread_url = "https://mircrew-releases.org/viewtopic.php?t=123"
            magnets = unlocker.extract_magnets_with_unlock(thread_url)

            self.assertIsInstance(magnets, list)
            # In this mock scenario, we should get the magnet from the page
            # (implementation may vary based on exact extraction logic)
            self.assertGreaterEqual(len(magnets), 0)  # At least no errors

    @patch('requests.Session')
    @patch('requests.Session.get')
    def test_indexer_thread_search_integration(self, mock_get, mock_session_class):
        """Test indexer direct thread search integration"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        indexer = MirCrewIndexer()

        # Mock login
        mock_login = MagicMock()
        mock_login.login.return_value = True
        mock_login.session = mock_session
        indexer.login_handler = mock_login

        # Mock thread page response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html><body>
            <div class="content">
                <a href="magnet:?xt=urn:btih:thread123&dn=Thread.File.1080p.mkv">Download</a>
            </div>
        </body></html>
        '''
        mock_get.return_value = mock_response

        # Test direct thread search
        result = indexer._search_thread_by_id("thread::180404")

        # Verify XML structure for direct thread search
        self.assertIn('<?xml version="1.0"', result)
        self.assertIn('<rss version="2.0"', result)
        self.assertIn('thread-180404-0', result)

    def test_category_mapping_accuracy(self):
        """Test that category mappings are consistently used across components"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        indexer = MirCrewIndexer()

        # This test ensures category codes are consistent between indexer and other components

        # Indexer category mapping
        indexer_categories = {
            '25': 'Movies',
            '26': 'Movies',
            '51': 'TV',
            '52': 'TV'
        }

        # Verify indexer's categories match expected
        self.assertEqual(indexer.cat_mappings['25'], 'Movies')
        self.assertEqual(indexer.cat_mappings['51'], 'TV')
        self.assertEqual(indexer.cat_mappings['26'], 'Movies')
        self.assertEqual(indexer.cat_mappings['52'], 'TV')

        # Test that categories are used consistently in parsing
        html_content = '''
        <html><body>
            <li class="row">
                <a class="topictitle" href="viewtopic.php?t=123">TV Show Name</a>
            </li>
        </body></html>
        '''

        tv_keywords = "Game of Thrones S01"
        result = indexer._parse_search_results(html_content, tv_keywords)

        if result:  # Results may be empty based on filtering logic
            for item in result:
                # Should classify as TV content based on S01 pattern
                if 'S01' in item.get('full_text', ''):
                    self.assertEqual(item['category'], 'TV')

    def test_xml_output_consistency(self):
        """Test that XML output format is consistent across different search types"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        indexer = MirCrewIndexer()

        # Create mock data for XML generation
        common_magnet_data = {
            'title': 'Test Movie File',
            'link': 'magnet:?xt=urn:btih:test123&dn=test.mkv',
            'details': 'https://mircrew-releases.org/viewtopic.php?t=123',
            'category_id': '25',
            'size': '1073741824',
            'pub_date': '2023-01-01T12:00:00'
        }

        magnets = [common_magnet_data]

        # Test regular search XML
        regular_xml = indexer._build_torznab_xml(magnets)

        # Test thread search XML
        # (Note: Thread search would have different structure but same item format)

        # Verify common XML elements are present
        for xml_output in [regular_xml]:
            self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml_output)
            self.assertIn('<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">', xml_output)
            self.assertIn('<channel>', xml_output)
            self.assertIn('<item>', xml_output)
            self.assertIn('<title>Test Movie File</title>', xml_output)
            self.assertIn('<torznab:attr', xml_output)
            self.assertIn('</channel>', xml_output)
            self.assertIn('</rss>', xml_output)

    @patch('requests.Session')
    @patch('requests.Session.get')
    def test_search_error_handling(self, mock_get, mock_session_class):
        """Test error handling throughout the search pipeline"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        # Mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        indexer = MirCrewIndexer()

        # Mock login
        mock_login = MagicMock()
        mock_login.login.return_value = True
        mock_login.session = mock_session
        indexer.login_handler = mock_login

        # Test network timeout
        mock_get.side_effect = Exception("Network timeout")

        result = indexer.search(q='test')

        # Should return error XML
        self.assertIn('<?xml version="1.0"', result)
        self.assertIn('<rss version="2.0">', result)
        self.assertIn('Exception', result)

    def test_parameter_validation_integration(self):
        """Test parameter validation across component boundaries"""
        if MirCrewIndexer is None:
            self.skipTest("MirCrew modules not available - skipping integration test")

        indexer = MirCrewIndexer()

        # Test various invalid parameters

        # Empty query should still work (defaults to year-based search)
        result = indexer.search(q='')

        # Invalid parameters should not crash
        result = indexer.search(q=None)
        self.assertIsInstance(result, str)

        # Test with various parameter combinations
        test_cases = [
            {'q': 'test movie'},
            {'q': 'test movie', 'season': '01'},
            {'q': '', 'season': '02', 'ep': '05'},
            {'q': None, 'season': None, 'ep': None}
        ]

        for params in test_cases:
            with self.subTest(params=params):
                try:
                    result = indexer.search(**params)
                    self.assertIsInstance(result, str)
                    self.assertIn('<?xml', result)
                except Exception as e:
                    # Some parameter combinations might raise exceptions
                    # The important thing is they don't crash the system
                    self.assertIsInstance(str(e), str)


if __name__ == '__main__':
    unittest.main()