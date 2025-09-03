"""Category mappings for MirCrew Indexer"""

from typing import Dict, Any

# Category mappings from mircrew.yml
# Maps MirCrew forum IDs to Newznab/Torznab categories
CATEGORY_MAPPINGS = {
    # Movies
    '25': {'id': '25', 'cat': 'Movies', 'desc': 'Video Releases'},
    '26': {'id': '26', 'cat': 'Movies', 'desc': 'Releases Film'},

    # TV
    '51': {'id': '51', 'cat': 'TV', 'desc': 'Releases TV Stagioni in corso'},
    '52': {'id': '52', 'cat': 'TV', 'desc': 'Releases TV Stagioni complete'},
    '29': {'id': '29', 'cat': 'TV/Documentary', 'desc': 'Documentari'},
    '30': {'id': '30', 'cat': 'TV', 'desc': 'TV Show'},
    '31': {'id': '31', 'cat': 'TV', 'desc': 'Teatro'},

    # Anime
    '33': {'id': '33', 'cat': 'TV/Anime', 'desc': 'Animazione Releases'},
    '34': {'id': '34', 'cat': 'Movies/Other', 'desc': 'Anime - Movies'},
    '35': {'id': '35', 'cat': 'TV/Anime', 'desc': 'Anime - Serie'},
    '36': {'id': '36', 'cat': 'Movies/Other', 'desc': 'Cartoon - Movies'},
    '37': {'id': '37', 'cat': 'TV/Anime', 'desc': 'Cartoon - Serie'},

    # Books
    '39': {'id': '39', 'cat': 'Books', 'desc': 'Libreria Releases'},
    '40': {'id': '40', 'cat': 'Books/EBook', 'desc': 'E-Books'},
    '41': {'id': '41', 'cat': 'Audio/Audiobook', 'desc': 'A-Books'},
    '42': {'id': '42', 'cat': 'Books/Comics', 'desc': 'Comics'},
    '43': {'id': '43', 'cat': 'Books/Mags', 'desc': 'Edicola'},

    # Audio
    '45': {'id': '45', 'cat': 'Audio', 'desc': 'Music Releases'},
    '46': {'id': '46', 'cat': 'Audio', 'desc': 'Musica - Audio'}
}

# Default sizes by category (from mircrew.yml torrent size mappings)
DEFAULT_SIZES = {
    'Movies': '10GB',
    'TV': '2GB',
    'TV/Documentary': '2GB',
    'TV/Anime': '2GB',
    'Movies/Other': '10GB',
    'Books': '512MB',
    'Books/EBook': '512MB',
    'Books/Comics': '512MB',
    'Books/Mags': '512MB',
    'Audio': '512MB',
    'Audio/Audiobook': '512MB'
}

def get_category_by_id(forum_id: str) -> Dict[str, Any]:
    """Get category mapping by forum ID"""
    return CATEGORY_MAPPINGS.get(forum_id, {'id': forum_id, 'cat': 'Other', 'desc': 'Unknown'})

def get_default_size(category: str) -> str:
    """Get default size for a category"""
    for key, size in DEFAULT_SIZES.items():
        if key in category:
            return size
    return '512MB'

def get_all_categories() -> Dict[str, Any]:
    """Get all category mappings"""
    return CATEGORY_MAPPINGS.copy()