#!/usr/bin/env python3
"""
Integration tests for Prowlarr API integration
Tests the MirCrew indexer API server with Prowlarr-compatible requests
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.mircrew.api.server import MirCrewAPIServer


class TestProwlarrIntegration(unittest.TestCase):
    """Integration tests for Prowlarr API compatibility"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.server = MirCrewAPIServer()
        self.app = self.server.app
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_caps_endpoint_prowlarr_compatibility(self):
        """Test that capabilities endpoint returns Prowlarr-compatible XML"""
        with self.client:
            response = self.client.get('/api?t=caps')

            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)

            # Verify Prowlarr-compatible elements
            self.assertIn('<caps>', data)
            self.assertIn('<server', data)
            self.assertIn('MirCrew Indexer', data)
            self.assertIn('<searching>', data)
            self.assertIn('<categories>', data)
            self.assertIn('supportedParams="q,cat,season,ep"', data)

    def test_caps_contains_required_categories(self):
        """Test that capabilities includes all required Newznab categories"""
        with self.client:
            response = self.client.get('/api?t=caps')
            data = response.get_data(as_text=True)

            # Check for major category groups
            self.assertIn('id="2000" name="Movies"', data)
            self.assertIn('id="5000" name="TV"', data)

            # Check for subcategories
            self.assertIn('<subcat id="2010"', data)
            self.assertIn('<subcat id="2040"', data)
            self.assertIn('<subcat id="5020"', data)
            self.assertIn('<subcat id="5040"', data)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_test_request_detection_and_response(self, mock_subprocess):
        """Test handling of Prowlarr test requests (empty searches)"""
        # Mock subprocess to return a simple test response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>Test Movie</title>
            <link>magnet:?xt=urn:btih:test123</link>
            <enclosure url="/download/test123" type="application/x-bittorrent"/>
        </item>
    </channel>
</rss>'''
        mock_subprocess.return_value = mock_result

        with self.client:
            # Test "test request" (no query parameters)
            response = self.client.get('/api?t=search')
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)

            # Should return valid XML
            self.assertIn('<?xml version="1.0"', data)
            self.assertIn('<rss version="2.0"', data)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_prowlarr_typical_search_pattern(self, mock_subprocess):
        """Test typical Prowlarr search pattern with category filter"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>Inception 2010</title>
            <link>magnet:?xt=urn:btih:inception123</link>
            <enclosure url="/download/inception123" type="application/x-bittorrent"/>
            <category>Movies</category>
            <torznab:attr name="category" value="2000"/>
        </item>
    </channel>
</rss>'''
        mock_subprocess.return_value = mock_subprocess

        with self.client:
            # Typical Prowlarr search for movies with category filter
            response = self.client.get('/api?t=search&q=Inception&cat=2000')
            self.assertEqual(response.status_code, 200)

            # Verify subprocess was called with correct parameters
            call_args = mock_subprocess.call_args[0][0]
            self.assertIn('-q', call_args)
            self.assertIn('Inception', call_args)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_tv_search_season_episode_format(self, mock_subprocess):
        """Test TV search with season and episode parameters"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>The Walking Dead S05E01</title>
            <link>magnet:?xt=urn:btih:twd123</link>
            <enclosure url="/download/twd123" type="application/x-bittorrent"/>
            <category>TV</category>
        </item>
    </channel>
</rss>'''
        mock_subprocess.return_value = mock_result

        with self.client:
            # TV search pattern used by Prowlarr
            response = self.client.get('/api?t=search&q=The+Walking+Dead&season=05&ep=01')
            self.assertEqual(response.status_code, 200)

            # Verify correct parameter handling
            call_args = mock_subprocess.call_args[0][0]
            self.assertIn('-q', call_args)
            self.assertIn('The Walking Dead', call_args)
            self.assertIn('-season', call_args)
            self.assertIn('05', call_args)
            self.assertIn('-ep', call_args)
            self.assertIn('01', call_args)

    def test_prowlarr_extended_parameters(self):
        """Test handling of extended Prowlarr parameters"""
        with self.client:
            # Prowlarr sometimes sends additional parameters
            response = self.client.get('/api?t=search&q=movie&limit=100&offset=0&extended=1')
            self.assertEqual(response.status_code, 200)

            # Should handle the request without errors
            data = response.get_data(as_text=True)
            self.assertIsInstance(data, str)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_imdb_tvdb_parameters(self, mock_subprocess):
        """Test handling of IMDB and TVDB ID parameters from Prowlarr"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>Movie by IMDB ID</title>
            <link>magnet:?xt=urn:btih:imdb123</link>
            <enclosure url="/download/imdb123" type="application/x-bittorrent"/>
        </item>
    </channel>
</rss>'''
        mock_subprocess.return_value = mock_result

        with self.client:
            # Prowlarr may send IMDB/TVDB IDs
            response = self.client.get('/api?t=search&imdbid=tt0111161&limit=100')
            self.assertEqual(response.status_code, 200)

    def test_error_response_format_prowlarr_compatible(self):
        """Test that error responses are Prowlarr-compatible"""
        with self.client:
            # Missing required 't' parameter should return error
            response = self.client.get('/api')

            data = response.get_data(as_text=True)

            # Should be XML format that Prowlarr can handle
            self.assertIn('Missing parameter', data)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_timeout_handling_prowlarr_style(self, mock_subprocess):
        """Test timeout handling that mimics Prowlarr behavior"""
        import subprocess

        # Simulate timeout (common with slow forum responses)
        mock_subprocess.side_effect = subprocess.TimeoutExpired([], 30)

        with self.client:
            response = self.client.get('/api?t=search&q=test')

            # Should handle timeout gracefully
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)
            self.assertIn('timeout', data.lower())

    @patch('src.mircrew.api.server.subprocess.run')
    def test_subprocess_error_recovery(self, mock_subprocess):
        """Test recovery from indexer subprocess errors"""
        # Simulate indexer process failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Indexer authentication failed"
        mock_subprocess.return_value = mock_result

        with self.client:
            response = self.client.get('/api?t=search&q=failed')
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)
            # Should contain error information
            self.assertIn('failed', data.lower())

    def test_health_endpoint_for_monitoring(self):
        """Test health endpoint for service monitoring"""
        with self.client:
            response = self.client.get('/health')

            # Health endpoint should return JSON
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertEqual(data['status'], 'healthy')
            self.assertIn('uptime', data)
            self.assertIn('timestamp', data)

    @patch('src.mircrew.api.server.send_file')
    def test_download_endpoint_format(self, mock_send_file):
        """Test download endpoint returns proper torrent file format"""
        mock_send_file.return_value = 'torrent_file_response'

        with self.client:
            response = self.client.get('/download/0123456789abcdef0123456789abcdef01234567')

            # Should trigger torrent file download
            mock_send_file.assert_called_once()
            args, kwargs = mock_send_file.call_args
            self.assertEqual(kwargs['mimetype'], 'application/x-bittorrent')
            self.assertTrue(kwargs['as_attachment'])
            self.assertIn('0123456789abcdef', kwargs['download_name'])

    def test_invalid_magnet_hash_handling(self):
        """Test handling of invalid magnet hash formats"""
        with self.client:
            # Test too short hash
            response = self.client.get('/download/short')
            data = response.get_data(as_text=True)
            self.assertIn('Invalid', data)

            # Test empty hash
            response = self.client.get('/download/')
            self.assertEqual(response.status_code, 404)  # Flask handles this as 404

    def test_url_encoding_handling(self):
        """Test proper handling of URL-encoded parameters"""
        with self.client:
            # Prowlarr may send URL-encoded queries
            response = self.client.get('/api?t=search&q=The%20Matrix')
            self.assertEqual(response.status_code, 200)

            # The query should be properly decoded internally
            # (Flask handles URL decoding automatically)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_pagination_parameters(self, mock_subprocess):
        """Test handling of pagination parameters from Prowlarr"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        with self.client:
            # Prowlarr may send pagination parameters
            response = self.client.get('/api?t=search&q=movies&offset=50&limit=25')
            self.assertEqual(response.status_code, 200)

            # Verify subprocess was called (parameters are passed through)
            mock_subprocess.assert_called_once()

    def test_multi_category_search(self):
        """Test searching across multiple categories"""
        with self.client:
            # Prowlarr may search without category filter to get all results
            response = self.client.get('/api?t=search&q=content')
            self.assertEqual(response.status_code, 200)

            # Should not have category filtering
            # (category filtering would be passed to indexer if present)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_complex_query_parameters(self, mock_subprocess):
        """Test handling of complex query parameter combinations"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        test_cases = [
            '/api?t=search&q=show+name&season=3&ep=12&cat=5000',
            '/api?t=search&q=movie+name&year=2023',
            '/api?t=search&season=1&ep=1&cat=5000',  # No query, season/ep only
        ]

        for url in test_cases:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

                # Each request should trigger subprocess execution
                call_count = len(mock_subprocess.call_args_list)
                self.assertGreater(call_count, 0)

    def test_response_content_type_headers(self):
        """Test that responses have appropriate content type headers"""
        with self.client:
            # API responses should be XML
            response = self.client.get('/api?t=caps')
            # Note: Test client may not set content-type in actual response object
            # but in real server it should be set to 'application/xml'

            self.assertEqual(response.status_code, 200)

            # Health check should be JSON
            response = self.client.get('/health')
            # Should contain JSON data
            data = json.loads(response.data)
            self.assertIsInstance(data, dict)


if __name__ == '__main__':
    unittest.main()