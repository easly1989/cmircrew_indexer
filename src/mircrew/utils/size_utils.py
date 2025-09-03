"""Size conversion utilities"""

from typing import Optional
import re


class SizeConverter:
    """Convert size strings to bytes and vice versa"""

    @staticmethod
    def parse_size(size_str: str) -> int:
        """
        Parse size string like '1.5GB' or '500MB' to bytes
        """
        if not size_str:
            return 0

        size_str = size_str.strip()

        # Match patterns like 1.5GB, 500MB, 1TB, etc.
        size_match = re.match(r'(\d+(?:\.\d+)?)\s*(GB|MB|TB|KB|B)', size_str.upper())

        if not size_match:
            # Try parsing as pure number (assume MB)
            try:
                return int(float(size_str) * 1024**2)  # Assume MB
            except ValueError:
                return 1024**3  # 1GB default

        value = float(size_match.group(1))
        unit = size_match.group(2)

        # Convert to bytes
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }

        return int(value * multipliers.get(unit, 1024**3))

    @staticmethod
    def format_bytes(bytes_size: int) -> str:
        """
        Format byte size to human readable format (GB, MB, etc.)
        """
        if bytes_size == 0:
            return "0B"

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(bytes_size)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)}{units[unit_index]}"
        else:
            return f"{size:.1f}{units[unit_index]}"

    @staticmethod
    def extract_size_from_text(text: str) -> Optional[str]:
        """
        Extract size information from text content (e.g., '1.5GB', '[2MB]', '(500MB)')
        """
        if not text:
            return None

        # Pattern to match size information in various formats
        patterns = [
            r'\b(\d+(?:\.\d+)?)\s*(GB|MB|TB|KB|B)\b',  # Regular format like "1.5GB"
            r'[\(\[](\d+(?:\.\d+)?)\s*(GB|MB|TB|KB|B)[\)\]]',  # Bracketed format like (1GB)
            r'\{(\d+(?:\.\d+)?)\s*(GB|MB|TB|KB|B)\}',  # Curly bracketed like {1GB}
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value, unit = match.groups()
                return value + unit.upper()

        return None


def convert_size_to_bytes(size_str: str) -> int:
    """
    Convenience function to convert size string to bytes
    """
    return SizeConverter.parse_size(size_str)


def convert_bytes_to_readable(bytes_int: int) -> str:
    """
    Convenience function to convert bytes to human readable format
    """
    return SizeConverter.format_bytes(bytes_int)


def get_default_size_for_category(category: str) -> str:
    """
    Get default size for a specific category
    """
    defaults = {
        'Movies': '10GB',
        'TV': '2GB',
        'TV/Documentary': '2GB',
        'Books': '512MB',
        'Audio': '512MB',
        'Other': '1GB'
    }

    # Try exact match
    if category in defaults:
        return defaults[category]

    # Try partial match
    for key, size in defaults.items():
        if key in category:
            return size

    return '1GB'  # Default fallback