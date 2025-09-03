#!/usr/bin/env python3
"""
Unit tests for MirCrew utility modules.

Tests cover XML helpers, size utilities, logging, and session management.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from src.mircrew.utils.xml_helpers import XMLHelper, TorznabXMLBuilder
from src.mircrew.utils.size_utils import SizeConverter, convert_size_to_bytes, get_default_size_for_category
from src.mircrew.utils.logging_utils import get_logger, setup_logging, set_log_level
from src.mircrew.utils.session import ThreadSafeSessionManager


class TestXMLHelper:
    """Test XML helper functions."""

    def test_escape_xml_basic_cases(self):
        """Test XML escaping for basic special characters."""
        xml_helper = XMLHelper()

        # Test individual special characters
        assert xml_helper.escape_xml('&') == '&'
        assert xml_helper.escape_xml('<test>') == '<test>'
        assert xml_helper.escape_xml('"quotes"') == '"quotes"'
        assert xml_helper.escape_xml("'apostrophe'") == "'apostrophe'"

    def test_escape_xml_combined(self):
        """Test XML escaping for strings with multiple special characters."""
        xml_helper = XMLHelper()

        # Complex string with multiple entities
        input_str = "Movie <The & \"Best\"> from '2024' & More"  # quotes are intentional
        expected = 'Movie <The & "Best"> from \'2024\' & More'
        result = xml_helper.escape_xml(input_str)
        assert result == expected

        # Make sure order is correct (no double escaping)
        assert '&' in result
        assert '&amp;' not in result  # Should not double-escape

    def test_escape_xml_edge_cases(self):
        """Test XML escaping for edge cases."""
        xml_helper = XMLHelper()

        # Empty string
        assert xml_helper.escape_xml("") == ""

        # None input
        assert xml_helper.escape_xml(None) == ""  # type: ignore # Testing None handling

        # Only normal characters
        normal = "Normal text without special chars"
        assert xml_helper.escape_xml(normal) == normal

    def test_format_datetime(self):
        """Test datetime formatting for XML."""
        xml_helper = XMLHelper()
        from datetime import datetime

        dt = datetime(2024, 9, 3, 15, 45, 30, 123456)
        formatted = xml_helper.format_datetime(dt)

        # Should end with Z and have milliseconds
        assert formatted.endswith('Z')
        assert '2024-09-03' in formatted
        assert '15:45:30' in formatted

    def test_validate_xml_valid(self):
        """Test XML validation for valid XML."""
        xml_helper = XMLHelper()

        valid_xml = '<?xml version="1.0"?><root><item>test</item></root>'
        assert xml_helper.validate_xml(valid_xml) is True

    def test_validate_xml_invalid(self):
        """Test XML validation for invalid XML."""
        xml_helper = XMLHelper()

        invalid_xml = '<?xml version="1.0"?><root><item>test</root>'  # Missing closing tag
        assert xml_helper.validate_xml(invalid_xml) is False

    def test_create_element(self):
        """Test element creation with attributes."""
        xml_helper = XMLHelper()

        elem = xml_helper.create_element('test', item_id='123', item_name='value')

        assert elem.tag == 'test'
        assert elem.get('item_id') == '123'
        assert elem.get('item_name') == 'value'

    def test_add_text_element(self):
        """Test adding text elements."""
        xml_helper = XMLHelper()

        parent = ET.Element('parent')
        child = xml_helper.add_text_element(parent, 'child', 'test content')

        assert child.tag == 'child'
        assert child.text == 'test content'
        assert child in list(parent)


class TestTorznabXMLBuilder:
    """Test Torznab XML generation."""

    def test_build_capabilities_has_required_elements(self):
        """Test capabilities XML contains required elements."""
        builder = TorznabXMLBuilder()
        xml_str = builder.build_capabilities()

        # Parse to verify structure
        root = ET.fromstring(xml_str)

        assert root.tag == 'caps'
        assert root.find('server') is not None
        assert root.find('limits') is not None
        assert root.find('searching') is not None
        assert root.find('categories') is not None

    def test_build_search_results(self):
        """Test search results XML generation."""
        builder = TorznabXMLBuilder()

        # Sample magnet data
        magnets = [{
            'title': 'Test.Release.AVI',
            'link': 'magnet:?xt=urn:btih:test123',
            'guid': 'magnet-test-1',
            'details': 'https://forum.example.com/test',
            'category': 'Movies',
            'size_bytes': 1000000000,
            'pub_date': '2024-09-03T15:00:00Z',
            'torznab_attrs': {'seeders': '1', 'peers': '2'}
        }]

        xml_str = builder.build_search_results(magnets)
        root = ET.fromstring(xml_str)

        assert root.tag == 'rss'
        channel = root.find('channel')
        assert channel is not None

        item = channel.find('item')
        assert item is not None

        title_elem = item.find('title')
        assert title_elem is not None
        assert title_elem.text == 'Test.Release.AVI'

        link_elem = item.find('link')
        assert link_elem is not None
        assert link_elem.text == 'magnet:?xt=urn:btih:test123'

        # Check torznab attributes
        torznab_attr = item.find('torznab:attr')
        assert torznab_attr is not None
        assert torznab_attr.get('name') == 'seeders'
        assert torznab_attr.get('value') == '1'

    def test_build_error_response(self):
        """Test error response XML generation."""
        builder = TorznabXMLBuilder()

        xml_str = builder.build_error_response('TEST_001', 'Sample error message')
        error_elem = ET.fromstring(xml_str)

        assert error_elem.get('code') == 'TEST_001'
        assert error_elem.get('description') == '<escape Error> Message'  # XML escaped


class TestSizeConverter:
    """Test size conversion utilities."""

    def test_parse_size_gb(self):
        """Test parsing GB sizes."""
        assert SizeConverter.parse_size('1GB') == 1000000000
        assert SizeConverter.parse_size('2.5GB') == 2500000000
        assert SizeConverter.parse_size('0.5GB') == 500000000

    def test_parse_size_mb(self):
        """Test parsing MB sizes."""
        assert SizeConverter.parse_size('512MB') == 512000000
        assert SizeConverter.parse_size('100MB') == 100000000

    def test_parse_size_tb(self):
        """Test parsing TB sizes."""
        assert SizeConverter.parse_size('1TB') == 1000000000000
        assert SizeConverter.parse_size('2TB') == 2000000000000

    def test_parse_size_with_whitespace(self):
        """Test parsing sizes with whitespace."""
        assert SizeConverter.parse_size('  1 GB  ') == 1000000000

    def test_parse_size_case_insensitive(self):
        """Test case-insensitive size parsing."""
        assert SizeConverter.parse_size('1gb') == 1000000000
        assert SizeConverter.parse_size('1Gb') == 1000000000
        assert SizeConverter.parse_size('1GB') == 1000000000

    def test_parse_size_fallback(self):
        """Test fallback parsing for unparseable sizes."""
        assert SizeConverter.parse_size('invalid') == 1073741824  # 1GB fallback
        assert SizeConverter.parse_size('') == 1073741824

    def test_format_bytes(self):
        """Test formatting bytes to human readable."""
        # Test various sizes
        assert SizeConverter.format_bytes(1000000000) == '1.0GB'
        assert SizeConverter.format_bytes(512000000) == '512.0MB'
        assert SizeConverter.format_bytes(1024) == '1KB'
        assert SizeConverter.format_bytes(1500) == '1500B'

    def test_format_bytes_edge_cases(self):
        """Test formatting edge cases."""
        assert SizeConverter.format_bytes(0) == '0B'
        assert SizeConverter.format_bytes(1) == '1B'

    def test_extract_size_from_text_regular(self):
        """Test size extraction from regular text."""
        assert SizeConverter.extract_size_from_text('Download 1.5GB file') == '1.5GB'
        assert SizeConverter.extract_size_from_text('Size: 512MB') == '512MB'

    def test_extract_size_from_text_bracketed(self):
        """Test size extraction from bracketed formats."""
        assert SizeConverter.extract_size_from_text('Movie [2GB]') == '2GB'
        assert SizeConverter.extract_size_from_text('Show (500MB)') == '500MB'
        assert SizeConverter.extract_size_from_text('File {1.5TB}') == '1.5TB'

    def test_extract_size_from_text_no_size(self):
        """Test size extraction when no size is present."""
        assert SizeConverter.extract_size_from_text('Normal text') is None
        assert SizeConverter.extract_size_from_text('') is None


class TestSizeUtilityFunctions:
    """Test standalone size utility functions."""

    def test_convert_size_to_bytes_function(self):
        """Test the convenience function."""
        assert convert_size_to_bytes('1GB') == 1000000000
        assert convert_size_to_bytes('512MB') == 512000000

    def test_get_default_size_for_category(self):
        """Test category-based size defaults."""
        assert get_default_size_for_category('Movies') == '10GB'
        assert get_default_size_for_category('TV') == '2GB'
        assert get_default_size_for_category('Books') == '512MB'
        assert get_default_size_for_category('Audio') == '512MB'

    def test_get_default_size_partial_match(self):
        """Test partial category matching."""
        assert get_default_size_for_category('TV Show') == '2GB'
        assert get_default_size_for_category('Documentary TV') == '2GB'

    def test_get_default_size_unknown(self):
        """Test fallback for unknown categories."""
        assert get_default_size_for_category('Unknown') == '1GB'
        assert get_default_size_for_category('XYZ Corp') == '1GB'


class TestLoggingUtils:
    """Test logging utility functions."""

    @patch('logging.config.dictConfig')
    def test_setup_logging(self, mock_dict_config):
        """Test logging setup function."""
        setup_logging()

        # Should call dictConfig
        mock_dict_config.assert_called_once()

    def test_get_logger(self):
        """Test logger retrieval function."""
        logger = get_logger('test_logger')

        assert logger.name == 'test_logger'
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'debug')

    @patch('logging.getLogger')
    def test_set_log_level(self, mock_get_logger):
        """Test setting log level."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        set_log_level('DEBUG')

        mock_logger.setLevel.assert_called_with(10)  # DEBUG level

        set_log_level('info')

        # Should handle case-insensitive level names
        assert mock_logger.setLevel.called


class TestSessionManager:
    """Test session management utilities."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_config = Mock()

    @patch('requests.Session')
    def test_thread_safe_session_manager_init(self, mock_session_class):
        """Test session manager initialization."""
        manager = ThreadSafeSessionManager(self.mock_config)

        assert manager.config == self.mock_config
        assert manager._session is None
        assert manager._authenticated is False
        assert hasattr(manager, '_lock')  # Should have a lock

    @patch('src.mircrew.utils.session.MirCrewLogin')
    @patch('requests.Session')
    def test_get_session_creates_new(self, mock_session_class, mock_login_class):
        """Test session creation when none exists."""
        # Configure mocks
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth.session = mock_session
        mock_login_class.return_value = mock_auth

        manager = ThreadSafeSessionManager(self.mock_config)
        session = manager.get_session()

        assert session == mock_session
        mock_session_class.assert_called_once()

    @patch('src.mircrew.utils.session.requests.Session')
    def test_get_session_reuse_existing(self, mock_session_class):
        """Test session reuse when already authenticated."""
        manager = ThreadSafeSessionManager(self.mock_config)
        manager._session = Mock()
        manager._authenticated = True

        session = manager.get_session()

        assert session == manager._session
        # Should not create a new session
        mock_session_class.assert_not_called()

    def test_is_authenticated_false_when_none(self):
        """Test authentication check when no session exists."""
        manager = ThreadSafeSessionManager(self.mock_config)
        assert manager.is_authenticated() is False

    def test_is_authenticated_true_when_valid(self):
        """Test authentication check with valid session."""
        manager = ThreadSafeSessionManager(self.mock_config)
        manager._session = Mock()
        manager._authenticated = True
        manager._last_check = float('inf')  # Never re-check

        assert manager.is_authenticated() is True

    def test_invalidate_session(self):
        """Test session invalidation."""
        manager = ThreadSafeSessionManager(self.mock_config)
        mock_session = Mock()
        manager._session = mock_session
        manager._authenticated = True

        manager.invalidate_session()

        assert manager._session is None
        assert manager._authenticated is False
        mock_session.close.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])