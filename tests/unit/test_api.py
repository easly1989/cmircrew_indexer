#!/usr/bin/env python3
"""
Unit tests for MirCrew API server Flask routes.

Tests cover all endpoints, input validation, error handling, and Prowlarr compatibility.
"""
import pytest
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from flask.testing import FlaskClient
from src.mircrew.api.server import MirCrewAPIServer


@pytest.fixture
def app():
    """Create and configure a test Flask app."""
    server = MirCrewAPIServer(host='127.0.0.1', port=9118)
    server.app.config['TESTING'] = True
    return server.app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing indexer calls."""
    with patch('src.mircrew.api.server.subprocess.run') as mock_run:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = '<?xml version="1.0"><test>success</test>'
        mock_process.stderr = ''
        mock_run.return_value = mock_process
        yield mock_run


class TestAPIRoutes:
    """Test all Flask API routes."""

    def test_health_endpoint_returns_json(self, client):
        """Test that /health endpoint returns proper JSON."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data.decode('utf-8'))

        required_keys = ['status', 'uptime', 'timestamp']
        for key in required_keys:
            assert key in data

        assert data['status'] == 'healthy'
        assert isinstance(data['uptime'], str)
        assert isinstance(data['timestamp'], str)

    def test_health_endpoint_content_type(self, client):
        """Test that /health returns JSON content type."""
        response = client.get('/health')
        assert 'application/json' in response.headers.get('Content-Type', '')

    @patch('src.mircrew.api.server.MirCrewAPIServer._create_torrent_from_magnet')
    def test_download_valid_magnet_hash(self, mock_create_torrent, client):
        """Test download endpoint with valid magnet hash."""
        mock_create_torrent.return_value = b'torrent_file_content'

        response = client.get('/download/abcdef0123456789abcdef0123456789abcdef')

        assert response.status_code == 200
        # Should have torrent file attachment
        assert 'attachment' in response.headers.get('Content-Disposition', '')
        assert 'application/x-bittorrent' in response.headers.get('Content-Type', '')

    def test_download_invalid_hash_length(self, client):
        """Test download endpoint rejects invalid hash length."""
        # Too short
        response = client.get('/download/short')
        assert response.status_code == 400
        assert b'Invalid magnet hash' in response.data

        # Too long
        response = client.get('/download/abcdef0123456789abcdef0123456789abcdef0123456789')
        assert response.status_code == 400
        assert b'Invalid magnet hash' in response.data

    def test_download_empty_hash(self, client):
        """Test download endpoint handles empty hash."""
        response = client.get('/download/')
        assert response.status_code == 404  # Flask renders this as 404 for empty path

    @patch('src.mircrew.api.server.MirCrewAPIServer._create_torrent_from_magnet')
    def test_download_server_error(self, mock_create_torrent, client):
        """Test download endpoint handles server errors gracefully."""
        mock_create_torrent.side_effect = Exception("Torrent creation failed")

        response = client.get('/download/abcdef0123456789abcdef0123456789abcdef')

        assert response.status_code == 500
        assert b'Error creating torrent file' in response.data


class TestTorznabAPI:
    """Test Torznab API functionality."""

    def test_missing_action_parameter(self, client):
        """Test API rejects requests without 't' parameter."""
        response = client.get('/api')
        assert response.status_code == 400
        data = response.data.decode('utf-8')
        assert '<error' in data
        assert 'Missing parameter' in data

    def test_invalid_action_parameter(self, client):
        """Test API rejects invalid 't' parameter values."""
        response = client.get('/api?t=invalid')
        assert response.status_code == 400
        data = response.data.decode('utf-8')
        assert '<error' in data
        assert 'Invalid action' in data

    def test_capabilities_response(self, client):
        """Test capabilities endpoint returns proper XML."""
        response = client.get('/api?t=caps')
        assert response.status_code == 200
        data = response.data.decode('utf-8')

        # Should contain required Torznab capabilities elements
        assert '<caps>' in data
        assert '<server' in data
        assert '<categories>' in data
        assert '<searching>' in data
        assert 'application/xml' in response.headers.get('Content-Type', '')


class TestSearchFunctionality:
    """Test search request handling."""

    def test_search_with_valid_parameters(self, client, mock_subprocess):
        """Test search works with proper parameters."""
        response = client.get('/api?t=search&q=The+Matrix&cat=2000')

        assert response.status_code == 200
        # Subprocess should have been called
        mock_subprocess.assert_called_once()

    def test_search_empty_query_handling(self, client, mock_subprocess):
        """Test search handles empty queries gracefully."""
        response = client.get('/api?t=search&q=')
        assert response.status_code == 200

    def test_search_with_season_episode(self, client, mock_subprocess):
        """Test search with season and episode parameters."""
        response = client.get('/api?t=search&season=1&ep=2')
        assert response.status_code == 200

    def test_search_with_special_characters(self, client, mock_subprocess):
        """Test search handles special characters in query."""
        response = client.get('/api?t=search&q=Movie%20Title%20%26%20More')
        assert response.status_code == 200

    def test_search_overlong_parameters(self, client, mock_subprocess):
        """Test search handles excessively long parameters."""
        long_query = 'A' * 1000  # Create a very long query
        response = client.get(f'/api?t=search&q={long_query}')
        assert response.status_code == 200  # Should still work due to sanitization

    def test_search_parameter_sanitization(self, client, mock_subprocess):
        """Test that dangerous parameters are sanitized."""
        response = client.get('/api?t=search&q=<script>alert(1)</script>')
        assert response.status_code == 200


class TestInputValidation:
    """Test input validation functions."""

    def setup_method(self):
        """Setup test server instance."""
        self.server = MirCrewAPIServer()

    def test_sanitize_numeric_parameter(self):
        """Test numeric parameter sanitization."""
        # Valid numeric input
        assert self.server._sanitize_numeric_param('123') == '123'
        assert self.server._sanitize_numeric_param('00123') == '00123'

        # Invalid or malicious input
        assert self.server._sanitize_numeric_param('abc123def') == '123'
        assert self.server._sanitize_numeric_param('<script>123</script>') == '123'

        # Empty input
        assert self.server._sanitize_numeric_param('') == ''
        assert self.server._sanitize_numeric_param(None) == ''

    def test_sanitize_limit_parameter(self):
        """Test limit parameter sanitization and bounds checking."""
        # Valid ranges
        assert self.server._sanitize_limit_param('50') == '50'
        assert self.server._sanitize_limit_param('100') == '100'

        # Bounds checking
        assert self.server._sanitize_limit_param('0') == '1'  # Minimum 1
        assert self.server._sanitize_limit_param('1000') == '500'  # Maximum 500
        assert self.server._sanitize_limit_param('600') == '500'  # Clamp upper bound

        # Invalid input fallback
        assert self.server._sanitize_limit_param('abc') == '100'
        assert self.server._sanitize_limit_param('') == '100'

    def test_sanitize_imdb_id(self):
        """Test IMDB ID sanitization."""
        # Valid IMDB IDs
        assert self.server._sanitize_imdb_id('tt0111161') == '0111161'
        assert self.server._sanitize_imdb_id('0111161') == '0111161'

        # Invalid input
        assert self.server._sanitize_imdb_id('ttXYZ123') == '123'
        assert self.server._sanitize_imdb_id('abcd') == ''

        # Empty input
        assert self.server._sanitize_imdb_id('') == ''

    def test_sanitize_query_parameters(self):
        """Test general query parameter sanitization."""
        # Normal input
        assert self.server._sanitize_query_param('The Matrix') == 'The Matrix'

        # Dangerous content removal
        assert self.server._sanitize_query_param('<script>alert(1)</script>') == 'scriptalert(1)/script'

        # Length limiting
        long_string = 'A' * 1000
        result = self.server._sanitize_query_param(long_string)
        assert len(result) <= 500  # Should be truncated

        # Empty input
        assert self.server._sanitize_query_param('') == ''
        assert self.server._sanitize_query_param(None) == ''


class TestProwlarrCompatibility:
    """Test Prowlarr compatibility features."""

    def test_prowlarr_test_request_detection(self, client, mock_subprocess):
        """Test detection of Prowlarr test requests."""
        # True test request: no parameters
        response = client.get('/api?t=search')
        assert response.status_code == 200
        # Should return test XML response, not call indexer
        mock_subprocess.assert_not_called()
        data = response.data.decode('utf-8')
        assert 'MirCrew.Indexer.Test.Response.SAMPLE.avi' in data

    def test_legitimate_search_with_empty_params(self, client, mock_subprocess):
        """Test that legitimate empty parameter searches are not mistaken for test requests."""
        # Empty query but with category specified
        response = client.get('/api?t=search&cat=2000')
        assert response.status_code == 200
        # Should call indexer for real search
        mock_subprocess.assert_called_once()

    def test_real_search_vs_test_request(self, client, mock_subprocess):
        """Test distinction between real searches and test requests."""
        # Test request with no parameters
        client.get('/api?t=search')
        # Should not call indexer for test requests
        initial_call_count = mock_subprocess.call_count

        # Real search with query
        client.get('/api?t=search&q=movie')
        # Should call indexer for real searches
        assert mock_subprocess.call_count > initial_call_count


class TestErrorHandling:
    """Test error handling and recovery."""

    def test_subprocess_failure(self, client, mock_subprocess):
        """Test handling of indexer subprocess failures."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = ''
        mock_process.stderr = 'Indexer failed with error'
        mock_subprocess.return_value = mock_process

        response = client.get('/api?t=search&q=The+Matrix')
        assert response.status_code == 500
        data = response.data.decode('utf-8')
        assert 'Indexer execution failed' in data

    def test_subprocess_timeout(self, client, mock_subprocess):
        """Test handling of indexer subprocess timeouts."""
        from src.mircrew.api.server import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=30)

        response = client.get('/api?t=search&t=test')
        assert response.status_code == 504
        data = response.data.decode('utf-8')
        assert 'timed out' in data

    @patch('src.mircrew.api.server.logger')
    def test_logging_of_api_errors(self, mock_logger, client):
        """Test that API errors are properly logged."""
        client.get('/api?t=invalid_action')

        # Should have logged the error
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        assert 'Invalid action' in call_args


class TestBencoding:
    """Test bencode implementation."""

    def setup_method(self):
        """Setup test server instance."""
        self.server = MirCrewAPIServer()

    def test_bencode_integer(self):
        """Test bencode integer encoding."""
        result = self.server._bencode(42)
        assert result == b'i42e'

        result = self.server._bencode(-1)
        assert result == b'i-1e'

    def test_bencode_string(self):
        """Test bencode string encoding."""
        result = self.server._bencode('hello')
        assert result == b'5:hello'

        result = self.server._bencode('')
        assert result == b'0:'

    def test_bencode_bytes(self):
        """Test bencode bytes encoding."""
        data = b'test_bytes'
        result = self.server._bencode(data)
        assert result == b'10:test_bytes'

    def test_bencode_list(self):
        """Test bencode list encoding."""
        result = self.server._bencode(['a', 'b', 42])
        assert result == b'l1:a1:bi42ee'

    def test_bencode_dict(self):
        """Test bencode dictionary encoding."""
        test_dict = {'key1': 'value1', 'key2': 42}
        result = self.server._bencode(test_dict)
        # Keys should be sorted in bencode
        expected = b'd4:key16:value14:key2i42ee'
        assert result == expected

    def test_bencode_unsupported_type(self):
        """Test bencode handles unsupported types gracefully."""
        with pytest.raises(ValueError, match="Unsupported type"):
            self.server._bencode(set(['unsupported']))


if __name__ == '__main__':
    pytest.main([__file__])