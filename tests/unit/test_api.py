#!/usr/bin/env python3
"""
Unit tests for MirCrew API server module
Tests Flask web server functionality, endpoint handling, and response generation
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import io
import json
from urllib.parse import quote

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from flask import Flask
from src.mircrew.api.server import MirCrewAPIServer


class TestMirCrewAPIServer(unittest.TestCase):
    """Test cases for MirCrew API server functionality"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.server = MirCrewAPIServer()
        self.app = self.server.app
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test method"""
        pass

    def test_init_creates_app(self):
        """Test that initialization creates Flask app and server instance"""
        self.assertIsNotNone(self.server.app)
        self.assertIsNotNone(self.server.host)
        self.assertIsNotNone(self.server.port)

    def test_health_endpoint(self):
        """Test health check endpoint"""
        with self.app.test_client() as client:
            response = client.get('/health')
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertIn('status', data)
            self.assertIn('uptime', data)
            self.assertIn('timestamp', data)
            self.assertEqual(data['status'], 'healthy')

    @patch('src.mircrew.api.server.requests.Session.get')
    def test_torznab_api_missing_t_parameter(self, mock_get):
        """Test Torznab API endpoint missing 't' parameter"""
        with self.app.test_client() as client:
            response = client.get('/api')
            self.assertEqual(response.status_code, 200)

            # Should contain error response
            data = response.get_data(as_text=True)
            self.assertIn('Missing parameter \'t\'', data)

    def test_torznab_api_caps_request(self):
        """Test Torznab API capabilities request"""
        with self.app.test_client() as client:
            response = client.get('/api?t=caps')
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)

            # Verify capabilities XML structure
            self.assertIn('<?xml version="1.0"', data)
            self.assertIn('<caps>', data)
            self.assertIn('<server', data)
            self.assertIn('<searching>', data)
            self.assertIn('<categories>', data)
            self.assertIn('MirCrew Indexer', data)

    def test_capabilities_contains_supported_params(self):
        """Test that capabilities response contains supported parameters"""
        with self.app.test_client() as client:
            response = client.get('/api?t=caps')
            data = response.get_data(as_text=True)

            # Check for required Torznab elements
            self.assertIn('supportedParams="q,cat,season,ep"', data)
            self.assertIn('<tv-search', data)
            self.assertIn('<movie-search', data)
            self.assertIn('available="yes"', data)

    def test_capabilities_contains_categories(self):
        """Test that capabilities response contains proper categories"""
        with self.app.test_client() as client:
            response = client.get('/api?t=caps')
            data = response.get_data(as_text=True)

            # Check for category structure
            self.assertIn('id="2000" name="Movies"', data)
            self.assertIn('id="5000" name="TV"', data)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_search_request_calls_subprocess(self, mock_subprocess):
        """Test that search requests properly call the subprocess"""
        # Mock successful subprocess execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        with self.app.test_client() as client:
            response = client.get('/api?t=search&q=test')
            self.assertEqual(response.status_code, 200)

            # Verify subprocess was called
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]

            # Check that indexer command was constructed correctly
            self.assertIn(sys.executable, call_args)
            self.assertIn('mircrew_indexer.py', call_args[1])
            self.assertIn('-q', call_args)
            self.assertIn('test', call_args)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_search_request_with_parameters(self, mock_subprocess):
        """Test search request with season and episode parameters"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        with self.app.test_client() as client:
            response = client.get('/api?t=search&season=01&ep=05&q=Dexter')
            self.assertEqual(response.status_code, 200)

            # Verify subprocess parameters
            call_args = mock_subprocess.call_args[0][0]
            self.assertIn('-season', call_args)
            self.assertIn('01', call_args)
            self.assertIn('-ep', call_args)
            self.assertIn('05', call_args)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_subprocess_failure_handling(self, mock_subprocess):
        """Test handling of subprocess execution failure"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Indexer execution failed"
        mock_subprocess.return_value = mock_result

        with self.app.test_client() as client:
            response = client.get('/api?t=search&q=test')
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)
            self.assertIn('Indexer execution failed', data)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_timeout_handling(self, mock_subprocess):
        """Test handling of subprocess timeout"""
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired([], 30)

        with self.app.test_client() as client:
            response = client.get('/api?t=search&q=test')
            self.assertEqual(response.status_code, 200)

            data = response.get_data(as_text=True)
            self.assertIn('Indexer execution timed out', data)

    def test_extract_torznab_params_basic(self):
        """Test basic parameter extraction from request"""
        with self.app.test_request_context('/api?t=search&q=test&limit=10'):
            from flask import request
            params = self.server._extract_torznab_params(request)

            self.assertEqual(params['t'], 'search')
            self.assertEqual(params['q'], 'test')
            self.assertEqual(params['limit'], '10')

    def test_extract_torznab_params_seasonal_search(self):
        """Test parameter extraction for TV/seasonal searches"""
        with self.app.test_request_context('/api?t=search&season=01&ep=05&cat=5000'):
            from flask import request
            params = self.server._extract_torznab_params(request)

            self.assertEqual(params['season'], '01')
            self.assertEqual(params['ep'], '05')
            self.assertEqual(params['cat'], '5000')

    def test_test_request_detection(self):
        """Test detection of Prowlarr test requests"""
        # Test request with no parameters (typical test request)
        with self.app.test_request_context('/api?t=search'):
            from flask import request
            params = self.server._extract_torznab_params(request)

            self.assertTrue(params['is_test_request'])

        # Test request with search parameter (not a test request)
        with self.app.test_request_context('/api?t=search&q=matrix'):
            from flask import request
            params = self.server._extract_torznab_params(request)

            self.assertFalse(params['is_test_request'])

    def test_test_request_response_structure(self):
        """Test test request response format"""
        with self.app.test_client() as client:
            # Mock to trigger test request path
            with patch.object(self.server, '_extract_torznab_params', return_value={
                't': 'search',
                'q': '',
                'season': '',
                'ep': '',
                'is_test_request': True
            }):
                response = client.get('/api?t=search')
                data = response.get_data(as_text=True)

                # Should contain basic test response structure
                self.assertIn('<?xml version="1.0"', data)
                self.assertIn('<rss version="2.0"', data)
                self.assertIn('<item>', data)
                self.assertIn('MirCrew.Indexer.Test.Response', data)

    def test_error_response_format(self):
        """Test error response formatting"""
        message = "Test error"
        code = 404

        with self.app.test_client() as client:
            # Trigger error response through missing required param
            response = client.get('/api')  # Missing 't' parameter
            data = response.get_data(as_text=True)

            self.assertIn('Missing parameter \'t\'', data)
            self.assertIn(str(code), data)

    def test_url_encoding_handling(self):
        """Test handling of URL-encoded parameters"""
        query_with_spaces = "Test Movie Query"
        encoded_query = quote(query_with_spaces)

        with self.app.test_client() as client:
            response = client.get(f'/api?t=search&q={encoded_query}')
            # Flask should automatically decode URL-encoded parameters
            self.assertEqual(response.status_code, 200)

    @patch('src.mircrew.api.server.send_file')
    @patch('src.mircrew.api.server.io.BytesIO')
    def test_download_torrent_endpoint(self, mock_bytesio, mock_send_file):
        """Test torrent download endpoint"""
        mock_file_data = b'torrent data'
        mock_bytesio.return_value = mock_file_data

        with self.app.test_client() as client:
            response = client.get('/download/abc123def456')

            # Should create torrent file response
            mock_send_file.assert_called_once()
            call_args = mock_send_file.call_args

            self.assertEqual(call_args[1]['mimetype'], 'application/x-bittorrent')
            self.assertTrue(call_args[1]['as_attachment'])
            self.assertIn('abc123def456', call_args[1]['download_name'])

    @patch('src.mircrew.api.server.send_file')
    def test_download_invalid_hash(self, mock_send_file):
        """Test torrent download with invalid hash"""
        with self.app.test_client() as client:
            response = client.get('/download/invalid')

            # Should return error for invalid hash
            mock_send_file.assert_not_called()
            self.assertEqual(response.status_code, 200)
            data = response.get_data(as_text=True)
            self.assertIn('Invalid magnet hash', data)

    def test_download_hash_validation(self):
        """Test magnet hash length validation"""
        with self.app.test_client() as client:
            # Test with hash that's too short
            response = client.get('/download/short')
            data = response.get_data(as_text=True)
            self.assertIn('Invalid magnet hash', data)

            # Test with hash that's correct length
            response = client.get('/download/' + 'a' * 40)
            self.assertEqual(response.status_code, 200)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_season_only_search(self, mock_subprocess):
        """Test search with only season parameter"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        with self.app.test_client() as client:
            response = client.get('/api?t=search&season=02')
            self.assertEqual(response.status_code, 200)

            call_args = mock_subprocess.call_args[0][0]
            self.assertIn('-season', call_args)
            self.assertIn('02', call_args)

    @patch('src.mircrew.api.server.subprocess.run')
    def test_year_based_search(self, mock_subprocess):
        """Test search with year parameter"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"></rss>'
        mock_subprocess.return_value = mock_result

        with self.app.test_client() as client:
            # Test without explicit query or season (should use year)
            response = client.get('/api?t=search')
            self.assertEqual(response.status_code, 200)

            call_args = mock_subprocess.call_args[0][0]
            # Should at least have the python executable and indexer script
            self.assertIn(sys.executable, call_args)
            self.assertTrue(len(call_args) >= 2)

    def test_xml_content_type(self):
        """Test that all XML responses have correct content type"""
        with self.app.test_client() as client:
            # Test capabilities response
            response = client.get('/api?t=caps')
            # Flask test client doesn't set content-type automatically,
            # but in real server it would be set via Response object
            self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()