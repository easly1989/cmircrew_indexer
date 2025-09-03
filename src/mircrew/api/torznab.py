"""Torznab XML generation utilities"""
from typing import List, Dict
import xml.etree.ElementTree as ET
from datetime import datetime

class TorznabXMLBuilder:
    """Builds Torznab-compliant XML responses"""

    @staticmethod
    def build_capabilities() -> str:
        """Build capabilities XML"""
        root = ET.Element("caps")

        server = ET.SubElement(root, "server")
        server.set("version", "1.0")
        server.set("title", "MirCrew Indexer")

        limits = ET.SubElement(root, "limits")
        limits.set("max", "100")
        limits.set("default", "50")

        # Add searching capabilities
        searching = ET.SubElement(root, "searching")
        search = ET.SubElement(searching, "search")
        search.set("available", "yes")
        search.set("supportedParams", "q,cat,season,ep")

        # Add categories
        categories = ET.SubElement(root, "categories")
        movies = ET.SubElement(categories, "category")
        movies.set("id", "2000")
        movies.set("name", "Movies")

        tv = ET.SubElement(categories, "category")
        tv.set("id", "5000")
        tv.set("name", "TV")

        return ET.tostring(root, encoding='unicode')

    @staticmethod
    def build_search_results(magnets: List[Dict]) -> str:
        """Build search results XML"""
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:torznab", "http://torznab.com/schemas/2015/feed")

        channel = ET.SubElement(rss, "channel")

        for i, magnet in enumerate(magnets):
            item = ET.SubElement(channel, "item")

            # Basic elements
            ET.SubElement(item, "title").text = magnet.get("title", "")
            ET.SubElement(item, "guid").text = f"magnet-{i}"
            ET.SubElement(item, "link").text = magnet.get("link", "")
            ET.SubElement(item, "pubDate").text = datetime.now().isoformat()
            ET.SubElement(item, "size").text = str(magnet.get("size_bytes", 0))

            # Torznab attributes
            for attr_name, attr_value in magnet.get("torznab_attrs", {}).items():
                attr_elem = ET.SubElement(item, "torznab:attr")
                attr_elem.set("name", attr_name)
                attr_elem.set("value", str(attr_value))

        return ET.tostring(rss, encoding='unicode')