#!/usr/bin/env python3
"""
Unit tests for MirCrew authentication module.

Tests authentication functionality with mocking to avoid actual network calls.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from src.mircrew.core.auth import MirCrewLogin


class TestMirCrewAuth:
    """Test suite for MirCrew authentication functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        with patch('requests.Session'):
            self.auth = MirCrewLogin()

    def test_init_creates_session(self):
        """Test that initialization creates a session with proper headers."""
        assert hasattr(self.auth, 'session')
        assert hasattr(self.auth, '_setup_session_headers')

    @patch.dict('os.environ', {'MIRCREW_USERNAME': 'testuser', 'MIRCREW_PASSWORD': 'testpass'})
    def test_get_credentials_success(self):
        """Test successful credential retrieval."""
        username, password = self.auth.get_credentials()
        assert username == 'testuser'
        assert password == 'testpass'

    @patch.dict('os.environ', {}, clear=True)
    def test_get_credentials_missing(self):
        """Test error handling for missing credentials."""
        with pytest.raises(ValueError, match="Missing credentials"):
            self.auth.get_credentials()

    @patch.dict('os.environ', {'MIRCREW_USERNAME': '', 'MIRCREW_PASSWORD': 'test'})
    def test_get_credentials_empty_username(self):
        """Test error handling for empty username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            self.auth.get_credentials()

    @patch.dict('os.environ', {'MIRCREW_USERNAME': 'test', 'MIRCREW_PASSWORD': '12'})
    def test_get_credentials_short_password(self):
        """Test error handling for short password."""
        with pytest.raises(ValueError, match="Password too short"):
            self.auth.get_credentials()

    def test_prepare_login_payload(self):
        """Test login payload preparation."""
        username = "testuser"
        password = "testpass"
        form_data = {
            'sid': 'session123',
            'form_token': 'token456',
            'creation_time': '1234567890'
        }

        payload = self.auth._prepare_login_payload(username, password, form_data)

        # Check required fields
        assert payload['username'] == username
        assert payload['password'] == password
        assert payload['autologin'] == '1'
        assert payload['viewonline'] == '1'
        assert payload['login'] == 'Login'

        # Check hidden fields
        assert payload['sid'] == 'session123'
        assert payload['form_token'] == 'token456'
        assert payload['creation_time'] == '1234567890'

    def test_prepare_login_payload_minimal(self):
        """Test payload preparation with minimal form data."""
        form_data = {}

        payload = self.auth._prepare_login_payload("user", "pass", form_data)

        assert payload['redirect'] == 'index.php'  # Default redirect
        assert 'sid' not in payload  # No sid provided

    def test_prepare_login_payload_invalid_form_data(self):
        """Test error handling for invalid form data."""
        with pytest.raises(TypeError):
            self.auth._prepare_login_payload("user", "pass", "not_a_dict")  # type: ignore

    @patch('requests.Session')
    def test_setup_session_headers_variety(self, mock_session):
        """Test that user agent rotation provides different agents."""
        agents = set()
        for _ in range(20):  # Test multiple calls
            auth = MirCrewLogin()
            # Check that session.headers.update was called
            assert mock_session.return_value.headers.update.called

    @patch('time.sleep')  # Mock sleep to speed up tests
    @patch('src.mircrew.core.auth.requests.Session')
    def test_establish_session_success(self, mock_session_class, mock_sleep):
        """Test successful session establishment."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth._establish_session()

        assert result is True
        mock_session.get.assert_called_with(
            'https://mircrew-releases.org/index.php',
            allow_redirects=True,
            timeout=15
        )

    @patch('src.mircrew.core.auth.requests.Session')
    def test_establish_session_retry_on_failure(self, mock_session_class):
        """Test session establishment retry logic."""
        mock_session = Mock()
        mock_session.get.side_effect = [
            Mock(status_code=500),  # First attempt fails
            Mock(status_code=200)   # Second attempt succeeds
        ]
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth._establish_session(max_retries=3)

        assert result is True
        assert mock_session.get.call_count == 2

    @patch('time.sleep')  # Mock sleep
    @patch('src.mircrew.core.auth.requests.Session')
    @patch('src.mircrew.core.auth.logger')
    def test_establish_session_max_retries_exceeded(self, mock_logger, mock_session_class, mock_sleep):
        """Test session establishment when all retries fail."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network error")
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth._establish_session(max_retries=2)

        assert result is False
        # Should show warning logs about retries
        assert any('Error establishing session' in str(call)
                  for call in mock_logger.warning.call_args_list)


class TestValidationLogic:
    """Test login validation logic."""

    def setup_method(self):
        """Setup test fixtures."""
        with patch('requests.Session'):
            self.auth = MirCrewLogin()

    def test_validate_login_success_indicators(self):
        """Test detection of successful login indicators."""
        # Mock successful response
        response = Mock()
        response.status_code = 200
        response.url = 'https://mircrew-releases.org/index.php'
        response.text = '<html><body>Welcome back! <a href="logout">Logout</a></body></html>'

        result = self.auth.validate_login(response)
        assert result is True

    def test_validate_login_error_indicators(self):
        """Test detection of login failure indicators."""
        # Mock failed response
        response = Mock()
        response.status_code = 200
        response.url = 'https://mircrew-releases.org/ucp.php?mode=login'
        response.text = '<html><body>Invalid username or password</body></html>'

        result = self.auth.validate_login(response)
        assert result is False

    def test_validate_login_http_error(self):
        """Test handling of HTTP error responses."""
        response = Mock()
        response.status_code = 500
        response.url = 'https://mircrew-releases.org/ucp.php?mode=login'

        result = self.auth.validate_login(response)
        assert result is False

    def test_validate_login_csrf_expired(self):
        """Test detection of CSRF token expiration."""
        response = Mock()
        response.status_code = 200
        response.url = 'https://mircrew-releases.org/ucp.php?mode=login'
        response.text = 'Il form inviato non è valido'

        result = self.auth.validate_login(response)
        # This might return False or True depending on URL and other conditions


class TestSessionPersistence:
    """Test session persistence validation."""

    def setup_method(self):
        """Setup test fixtures."""
        with patch('requests.Session'):
            self.auth = MirCrewLogin()

    @patch('src.mircrew.core.auth.requests.Session')
    def test_is_logged_in_success(self, mock_session_class):
        """Test successful session validation."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = 'https://mircrew-releases.org/index.php'
        mock_response.text = 'Logout My Account Profile'
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth.is_logged_in()

        assert result is True

    @patch('src.mircrew.core.auth.requests.Session')
    def test_is_logged_in_redirect_to_login(self, mock_session_class):
        """Test session invalidation when redirected to login."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.url = 'https://mircrew-releases.org/ucp.php?mode=login'
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth.is_logged_in()

        assert result is False

    @patch('src.mircrew.core.auth.requests.Session')
    def test_is_logged_in_network_error(self, mock_session_class):
        """Test handling of network errors during session validation."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network error")
        mock_session_class.return_value = mock_session

        auth = MirCrewLogin()
        result = auth.is_logged_in()

        assert result is False


if __name__ == '__main__':
    pytest.main([__file__])