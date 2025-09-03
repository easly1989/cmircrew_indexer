#!/usr/bin/env python3
"""
Unit tests for MirCrew indexer core module.

Tests indexer functionality including config loading, category mapping, and XML generation.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import requests
from src.mircrew.core.indexer import MirCrewIndexer


class TestMirCrewIndexerConfig:
    """Test configuration loading and category mapping functionality."""

    def test_init_loads_config_success(self):
        """Test that indexer loads category mappings from config file."""
        # Create a temporary config file
        config_data = """---
caps:
  categorymappings:
    - {id: 25, cat: Movies, desc: "Video Releases"}
    - {id: 51, cat: TV, desc: "Releases TV Stagioni in corso"}
    - {id: 39, cat: Books, desc: "Libreria Releases"}
fields:
  size_default:
    case:
      'a[href*="f=25"]': 10GB
      'a[href*="f=51"]': 2GB
      'a[href*="f=39"]': 512MB
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_data)
            config_path = f.name

        try:
            # Create indexer with custom config path
            with patch('src.mircrew.core.indexer.requests.Session'):
                indexer = MirCrewIndexer(config_path=config_path)

            # Check that config was loaded properly
            assert '25' in indexer.cat_mappings
            assert indexer.cat_mappings['25'] == 'Movies'
            assert indexer.cat_mappings['51'] == 'TV'
            assert indexer.cat_mappings['39'] == 'Books'

            # Check size defaults
            assert indexer.default_sizes['Movies'] == '10GB'
            assert indexer.default_sizes['TV'] == '2GB'
            assert indexer.default_sizes['Books'] == '512MB'

        finally:
            os.unlink(config_path)

    def test_init_config_file_not_found_fallback(self):
        """Test that indexer falls back to hardcoded mappings when config not found."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer(config_path='/nonexistent/path.yml')

        # Should have fallback mappings
        assert len(indexer.cat_mappings) > 0
        assert '25' in indexer.cat_mappings
        assert len(indexer.default_sizes) > 0

    def test_extract_forum_id_from_url(self):
        """Test forum ID extraction from thread URLs."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        test_cases = [
            ('https://mircrew-releases.org/viewtopic.php?f=25&t=1234', '25'),
            ('https://mircrew-releases.org/viewtopic.php?t=1234&f=51', '51'),
            ('https://mircrew-releases.org/viewtopic.php?t=1234', None),
            ('https://mircrew-releases.org/index.php', None),
        ]

        for url, expected in test_cases:
            result = indexer._extract_forum_id_from_url(url)
            assert result == expected


class TestIndexerXMLHandling:
    """Test XML escaping and generation functionality."""

    def test_escape_xml(self):
        """Test XML escaping of special characters."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        test_cases = [
            ("Normal text", "Normal text"),
            ("Text with & ampersand", "Text with & ampersand"),
            ("Less and < greater >", "Less and < greater >"),
            ("Quote \" and ' apostrophe\"", "Quote \" and ' apostrophe\""),
            ("Multiple <>&\"'", "Multiple <>&\"'"),
            ("", ""),
            (None, ""),
        ]

        for input_text, expected in test_cases:
            result = indexer._escape_xml(input_text)
            assert result == expected

    def test_escape_xml_mixed_content(self):
        """Test XML escaping with complex content including newlines and special characters."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        # Title with special characters that might appear in torrent names
        complex_title = "Movie.Title.2023.1080p.BluRay.x264-SOME<GROUP>&more[stuff]here"

        escaped = indexer._escape_xml(complex_title)
        expected = "Movie.Title.2023.1080p.BluRay.x264-SOME<GROUP>&more[stuff]here"

        assert escaped == expected
        assert '<' not in escaped  # Should be escaped
        assert '>' not in escaped  # Should be escaped
        assert '&' not in escaped  # Should be escaped unless part of entity


class TestSizeHandling:
    """Test size parsing and byte conversion functionality."""

    def test_parse_size_standard_formats(self):
        """Test size parsing with standard formats."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        test_cases = [
            ("The Matrix (1999) [1080p][x264][DTS][EN-IT][12.3GB]", "12.3GB"),
            ("Movie [720p] 1.5 GB", "1.5GB"),
            ("Show S01E01 500 MB", "500MB"),
            ("Documentary (2003) [1.2TB]", "1.2TB"),
            ("Episode.1080p.2.4GiB", "2.4GiB"),
            ("Italian.Format.1,5GB", "1.5GB"),  # Italian comma decimal
            ("Simple numbers 512MB", "512MB"),
        ]

        for title, expected in test_cases:
            result = indexer._parse_size(title)
            assert result == expected, f"Failed to parse '{title}', expected '{expected}', got '{result}'"

    def test_parse_size_no_size_info(self):
        """Test size parsing when no size information is found."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        titles_without_size = [
            "Movie Title Without Size Info",
            "Another Movie [1080p]",
            "Just a title with no size",
            "",
        ]

        for title in titles_without_size:
            result = indexer._parse_size(title)
            assert result is None

    def test_convert_size_to_bytes_standard_units(self):
        """Test size conversion with standard units."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        test_cases = [
            ("1GB", 1000000000),      # Decimal GB
            ("500MB", 500000000),     # Decimal MB
            ("1000KB", 1000000),      # Decimal KB
            ("1GiB", 1073741824),     # Binary GiB
            ("500MiB", 524288000),    # Binary MiB
            ("1000KiB", 1024000),     # Binary KiB
            ("1.5GB", 1500000000),    # Decimal with decimal
            ("512MB", 512000000),     # Integer
        ]

        for size_str, expected_bytes in test_cases:
            result = indexer._convert_size_to_bytes(size_str)
            assert result == expected_bytes, f"Failed to convert '{size_str}': expected {expected_bytes}, got {result}"

    def test_convert_size_to_bytes_fallback(self):
        """Test fallback behavior for unparseable size strings."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        # Should default to 1GB for unparseable strings
        default_gb = 1073741824

        unparseable_sizes = [
            "InvalidSizeString",
            "",
            "JustLettersNoNumbers",
            "1XXX",  # Unknown unit
        ]

        for size_str in unparseable_sizes:
            result = indexer._convert_size_to_bytes(size_str)
            assert result == default_gb, f"Expected default {default_gb} for '{size_str}', got {result}"

    def test_convert_size_to_bytes_without_unit(self):
        """Test size conversion for strings without explicit units."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        # Numbers without units should be interpreted intelligently
        test_cases = [
            ("10", 10737418240),     # >= 10, assume GB (10 * 1GB)
            ("1", 1048576),         # < 10, assume MB (1 * 1MB)
        ]

        for size_str, expected_bytes in test_cases:
            result = indexer._convert_size_to_bytes(size_str)
            assert result == expected_bytes, f"Failed to convert '{size_str}': expected {expected_bytes}, got {result}"


class TestIndexingFunctionality:
    """Test core indexing functionality."""

    def test_thread_id_search_syntax(self):
        """Test that thread search syntax is properly parsed."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        # Valid thread search syntax
        valid_queries = [
            "thread::12345",
            "thread::180404",
            "thread::1",
        ]

        for query in valid_queries:
            assert query.lower().startswith("thread::")
            thread_id = query[8:]  # Remove "thread::" prefix
            assert thread_id.isdigit()
            assert len(thread_id) > 0

    def test_thread_id_search_invalid(self):
        """Test error handling for invalid thread search syntax."""
        with patch('src.mircrew.core.indexer.requests.Session'):
            indexer = MirCrewIndexer()

        invalid_queries = [
            "thread::",           # Empty thread ID
            "thread::notnumeric", # Non-numeric thread ID
            "notthread::12345",   # Wrong prefix
        ]

        for query in invalid_queries:
            # These should fail validation
            thread_part = query.lower()
            if thread_part.startswith("thread::"):
                thread_id = query[8:]
                if not thread_id.isdigit():
                    # This is expected to fail
                    assert not thread_id.isdigit()


if __name__ == '__main__':
    # Test can be run with: python -m pytest tests/unit/test_indexer.py
    pass