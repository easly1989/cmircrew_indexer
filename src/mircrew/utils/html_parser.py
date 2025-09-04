"""
HTML Parsing Module - Dedicated to BeautifulSoup parsing with type safety
"""
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag
import re

@dataclass
class ThreadInfo:
    title: str
    url: str
    category: str
    date: Optional[str]
    id: str

@dataclass
class MagnetInfo:
    url: str
    thread_title: str
    thread_id: str
    category: str

class ForumParser:
    """Parser for forum thread listings and thread content"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        
    def parse_search_results(self, html_content: str) -> List[ThreadInfo]:
        """Parse search results page into structured thread info"""
        soup = BeautifulSoup(html_content, 'html.parser')
        threads = []
        
        for row in soup.find_all('li', class_='row'):
            try:
                title_link = self._safe_find(row, 'a', {'class': 'topictitle'})
                if not title_link or not title_link.get('href'):
                    continue

                title = title_link.get_text(strip=True)
                thread_url = self._make_absolute_url(str(title_link['href']))  # type: ignore[index]
                
                time_elem = self._safe_find(row, 'time', {'datetime': True})
                date_info = str(time_elem.get('datetime')) if time_elem else None  # type: ignore[union-attr]
                
                threads.append(ThreadInfo(
                    title=title,
                    url=thread_url,
                    category="Movies",  # Default, will be refined in Phase 3
                    date=date_info,
                    id=self._extract_thread_id(thread_url)
                ))
            except Exception as e:
                # Log parsing errors but continue processing
                continue
                
        return threads
    
    def parse_thread_content(self, html_content: str) -> List[MagnetInfo]:
        """Parse thread content page into structured magnet info"""
        # Placeholder implementation - will be completed in next iteration
        return []

    def _safe_find(self, parent, name: str, attrs: Optional[Dict] = None) -> Optional[Tag]:
        """Type-safe element finding with error handling"""
        try:
            return parent.find(name, attrs=attrs)
        except Exception:
            return None
            
    def _make_absolute_url(self, path: str) -> str:
        """Convert relative path to absolute URL"""
        return f"{self.base_url}/{path.lstrip('/')}"
        
    def _extract_thread_id(self, url: str) -> str:
        """Extract thread ID from URL"""
        match = re.search(r't=(\d+)', url)
        return match.group(1) if match else 'unknown'

class MagnetParser:
    """Dedicated parser for magnet link extraction"""
    
    MAGNET_PATTERNS = [
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}',  # Standard 40-char hash
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32}',  # Shorter hash
        r'magnet:\?xt=urn:btih%3A[a-zA-Z0-9%]{40,}',  # URL-encoded
        r'magnet:\?[a-z]+=[^&]+&(?:.*&)*xt=urn:btih:[a-zA-Z0-9]{20,}',  # With parameters
        r'magnet:\?xt=urn:btih:[^\'"\s<>&]{32,}'  # More flexible matching
    ]
    
    def find_magnets(self, soup: BeautifulSoup) -> List[str]:
        """Find all magnet links using multiple strategies"""
        magnets = set()
        
        # Try different extraction strategies
        magnets.update(self._find_in_links(soup))
        magnets.update(self._find_in_text(soup))
        magnets.update(self._find_in_attributes(soup))
        magnets.update(self._find_in_code(soup))
        
        return list(magnets)
    
    def _find_in_links(self, soup: BeautifulSoup) -> List[str]:
        """Find magnets in direct <a> tags"""
        found = []
        for pattern in self.MAGNET_PATTERNS:
            for link in soup.find_all('a', href=re.compile(pattern, re.IGNORECASE)):
                if href := link.get('href', ''):  # type: ignore[union-attr]
                    found.append(str(href).strip())
        return found
    
    def _find_in_text(self, soup: BeautifulSoup) -> List[str]:
        """Find magnets in text content"""
        found = []
        text_elements = soup.find_all(['div', 'p', 'code', 'span', 'blockquote'])
        for element in text_elements:
            text_content = element.get_text()
            for pattern in self.MAGNET_PATTERNS:
                found.extend(re.findall(pattern, text_content, re.IGNORECASE))
        return found
    
    def _find_in_attributes(self, soup: BeautifulSoup) -> List[str]:
        """Find magnets in HTML attributes"""
        found = []
        attr_patterns = ['onclick', 'data-href', 'data-magnet', 'value']
        for attr in attr_patterns:
            for element in soup.find_all(attrs={attr: True}):
                attr_value = str(element.get(attr, ''))  # type: ignore[union-attr]
                for pattern in self.MAGNET_PATTERNS:
                    found.extend(re.findall(pattern, attr_value, re.IGNORECASE))
        return found
    
    def _find_in_code(self, soup: BeautifulSoup) -> List[str]:
        """Find magnets in code blocks"""
        found = []
        code_elements = soup.find_all(['pre', 'code', 'div'], 
                                    class_=re.compile(r'code|bbcode|forumcode'))
        for element in code_elements:
            text_content = element.get_text()
            for pattern in self.MAGNET_PATTERNS:
                found.extend(re.findall(pattern, text_content, re.IGNORECASE))
        return found