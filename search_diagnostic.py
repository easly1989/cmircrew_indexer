#!/usr/bin/env python3
"""
Diagnostic search script for mircrew-releases.org
Tests different search parameters to find Matrix-related threads
"""

import sys
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Import login module
sys.path.insert(0, os.path.dirname(__file__))
from login import MirCrewLogin

def diagnostic_search(query="Matrix", test_cases=None):
    """Test different search parameters to find what works"""

    print(f"🔍 Diagnostic search for '{query}' on mircrew-releases.org")
    print("=" * 60)

    # Set up session and authenticate
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    login_client = MirCrewLogin()
    if not login_client.login():
        print("❌ Authentication failed")
        return

    session = login_client.session
    base_url = "https://mircrew-releases.org"

    # Determine appropriate categories based on query
    if 'dexter' in query.lower():
        # TV categories for Dexter
        categories = ['51', '52', '29', '30']
    else:
        # Movies categories for Matrix (default)
        categories = ['25', '26']

    # Test cases to try
    if not test_cases:
        test_cases = [
            {
                'name': 'Simple search with titles+content',
                'params': [ ('keywords', query), ('scf', '1'), ('sr', 'topics'), ('sk', 't'),
                           ('sd', 'd'), ('st', '0'), ('ch', '50') ] + [('fid[]', cat) for cat in categories]
            },
            {
                'name': 'Title-only search (Working Method)',
                'params': [ ('keywords', query), ('sf', 'titleonly'), ('sr', 'topics'), ('sk', 't'),
                           ('sd', 'd'), ('st', '0'), ('ch', '50') ] + [('fid[]', cat) for cat in categories[:2]]
            },
            {
                'name': 'Title search with multiple categories',
                'params': [ ('keywords', query), ('sf', 'titleonly'), ('sr', 'topics'), ('sk', 't'),
                           ('sd', 'd'), ('st', '0'), ('ch', '50') ] + [('fid[]', cat) for cat in categories]
            }
        ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔬 Test {i}: {test_case['name']}")
        print("-" * 40)

        try:
            # Execute search
            response = session.get(f"{base_url}/search.php", params=test_case['params'], timeout=30, allow_redirects=True)

            if response.status_code != 200:
                print(f"❌ Failed with status {response.status_code}")
                continue

            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for different sources of results
            results = []

            # Check for search results container
            result_containers = soup.find_all(['li', 'div'], class_=re.compile(r'row|search-result'))

            for container in result_containers[:10]:  # Limit to first 10
                title_links = container.find_all('a', class_='topictitle')
                for link in title_links:
                    title = link.get_text(strip=True)
                    if title and len(title) > 2:  # Filter meaningful titles
                        results.append(title[:100])  # Truncate long titles

            print(f"📊 Found {len(results)} potential results:")

            # IMPROVED: Enhanced relevance detection for partial/substring matches
            relevant = []
            not_relevant = []

            # Also handle partial matches like "Matrix" in "Animatrix", "Dexter:" in "Dexter: Resurrection"
            for result in results:
                result_lower = result.lower()
                search_terms = query.lower().split()

                # Check if ALL search terms appear in the title (with substring flexibility)
                all_terms_match = True
                for term in search_terms:
                    if not self._contains_partial_match(term, result_lower):
                        all_terms_match = False
                        break

                if all_terms_match:
                    relevant.append(result)
                else:
                    not_relevant.append(result)

    def _contains_partial_match(self, query_term, title_text):
        """Flexible matching that handles partial/strings within words"""
        # Direct substring match (handles "Matrix" in "Animatrix")
        if query_term in title_text:
            return True

        # Handle cases like "Dexter:" in "Dexter: Resurrection" (phrase prefix)
        for word in title_text.split():
            # Check if query term is at start of word
            if word.lower().startswith(query_term) or query_term.startswith(word.lower()):
                return True

            # Handle hyphenated words
            if '-' in word:
                parts = word.split('-')
                if any(part.lower() == query_term or part.lower().startswith(query_term) for part in parts):
                    return True

        return False

            print(f"   ✅ {query}-related: {len(relevant)}")
            if relevant:
                for title in relevant[:5]:  # Show first 5
                    print(f"      • {title}")

            print(f"   ❌ Not {query}-related: {len(not_relevant)}")
            if not_relevant and len(not_relevant) <= 3:
                for title in not_relevant:
                    print(f"      • {title}")

        except Exception as e:
            print(f"❌ Search failed: {e}")

    print("\n" + "=" * 60)
    print("Diagnostic complete! Review results above.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='MirCrew Search Diagnostics')
    parser.add_argument('-q', '--query', default='Matrix', help='Search term to test')
    args = parser.parse_args()

    diagnostic_search(args.query)