"""XML parsing and generation utilities"""
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime


class XMLHelper:
    """XML utilities for Torznab compatibility"""

    @staticmethod
    def create_element(name: str, **attrs) -> ET.Element:
        """Create XML element with attributes"""
        elem = ET.Element(name)
        for key, value in attrs.items():
            elem.set(key, str(value))
        return elem

    @staticmethod
    def add_text_element(parent: ET.Element, name: str, text: str) -> ET.Element:
        """Add text element to parent"""
        elem = ET.SubElement(parent, name)
        elem.text = text
        return elem

    @staticmethod
    def add_attribute_element(parent: ET.Element, name: str, attrs: Dict[str, Any]) -> ET.Element:
        """Add attribute element to parent (Torznab format)"""
        elem = ET.SubElement(parent, 'torznab:attr')
        elem.set('name', name)
        elem.set('value', str(attrs.get('value', '')))
        return elem

    @staticmethod
    def escape_xml(text: str) -> str:
        """Escape XML special characters"""
        if not text:
            return ""
        replacements = [('&', '&amp;amp;'), ('<', '&amp;lt;'), ('>', '&gt;'), ('"', '&quot;'), ("'", '&apos;')]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

        return text

    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime for XML"""
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'

    @staticmethod
    def validate_xml(xml_string: str) -> bool:
        """Validate XML string"""
        try:
            ET.fromstring(xml_string)
            return True
        except ET.ParseError:
            return False


class TorznabXMLBuilder:
    """Enhanced Torznab XML builder"""

    def __init__(self):
        self.xml_helper = XMLHelper()

    def build_capabilities(self, categories: Optional[Dict[str, Any]] = None) -> str:
        """Build Torznab capabilities XML"""
        caps = self.xml_helper.create_element('caps')

        # Server info
        server = ET.SubElement(caps, 'server')
        server.set('version', '1.0')
        server.set('title', 'MirCrew Indexer')
        server.set('strapline', 'MirCrew Indexer API')
        server.set('email', 'support@example.com')
        server.set('url', 'http://localhost:9118')
        server.set('image', 'http://localhost:9118/api')

        # Limits
        limits = ET.SubElement(caps, 'limits')
        limits.set('max', '100')
        limits.set('default', '50')

        # Registration
        reg = ET.SubElement(caps, 'registration')
        reg.set('available', 'no')
        reg.set('open', 'no')

        # Searching capabilities
        searching = ET.SubElement(caps, 'searching')
        search = ET.SubElement(searching, 'search')
        search.set('available', 'yes')
        search.set('supportedParams', 'q,cat')

        tv_search = ET.SubElement(searching, 'tv-search')
        tv_search.set('available', 'yes')
        tv_search.set('supportedParams', 'q,cat,season,ep')

        movie_search = ET.SubElement(searching, 'movie-search')
        movie_search.set('available', 'yes')
        movie_search.set('supportedParams', 'q,cat')

        # Categories
        cats = ET.SubElement(caps, 'categories')

        # Movies category
        movies = ET.SubElement(cats, 'category')
        movies.set('id', '2000')
        movies.set('name', 'Movies')
        ET.SubElement(movies, 'subcat').set('id', '2010')
        ET.SubElement(movies, 'subcat').set('id', '2040')

        # TV category
        tv = ET.SubElement(cats, 'category')
        tv.set('id', '5000')
        tv.set('name', 'TV')
        ET.SubElement(tv, 'subcat').set('id', '5020')
        ET.SubElement(tv, 'subcat').set('id', '5040')

        return ET.tostring(caps, encoding='unicode')

    def build_search_results(self, magnets: List[Dict[str, Any]]) -> str:
        """Build search results XML"""
        rss = self.xml_helper.create_element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:torznab', 'http://torznab.com/schemas/2015/feed')

        channel = ET.SubElement(rss, 'channel')

        for i, magnet in enumerate(magnets):
            item = ET.SubElement(channel, 'item')

            # Title
            self.xml_helper.add_text_element(item, 'title', magnet.get('title', ''))

            # GUID
            guid = magnet.get('guid', f'magnet-{i}')
            self.xml_helper.add_text_element(item, 'guid', guid)

            # Link
            self.xml_helper.add_text_element(item, 'link', magnet.get('link', ''))

            # Comments
            self.xml_helper.add_text_element(item, 'comments', magnet.get('details', ''))

            # Publication date
            pub_date = magnet.get('pub_date', '')
            if isinstance(pub_date, datetime):
                pub_date = self.xml_helper.format_datetime(pub_date)
            self.xml_helper.add_text_element(item, 'pubDate', pub_date)

            # Category
            self.xml_helper.add_text_element(item, 'category', magnet.get('category', ''))

            # Size
            size_bytes = magnet.get('size_bytes', 0)
            self.xml_helper.add_text_element(item, 'size', str(size_bytes))

            # Description
            description = magnet.get('description', '')
            self.xml_helper.add_text_element(item, 'description', description)

            # Torznab attributes
            torznab_attrs = magnet.get('torznab_attrs', {})
            for name, value in torznab_attrs.items():
                ET.SubElement(item, 'torznab:attr', {'name': name, 'value': str(value)})

        return ET.tostring(rss, encoding='unicode')

    def build_error_response(self, error_code: str, description: str) -> str:
        """Build error response XML"""
        error = self.xml_helper.create_element('error')
        error.set('code', str(error_code))
        error.set('description', self.xml_helper.escape_xml(description))

        return ET.tostring(error, encoding='unicode')