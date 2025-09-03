#!/usr/bin/env python3
"""
REVISED: Advanced MirCrew search diagnostic with improved relevance matching
Handles partial/substring matches like "Matrix" in "Animatrix"
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

def contains_partial_match(query_term, title_text):
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

        # Handle words with colons
        if ':' in word:
            parts = word.split(':')
            if any(part.lower().strip() == query_term or part.lower().strip().startswith(query_term) for part in parts):
                return True

    return False

def diagnostic_search(query="Matrix", test_cases=None):
    """Test different search parameters to find what works"""

    print(f"🔍 Enhanced Diagnostic search for '{query}' on mircrew-releases.org")
    print("=" * 70)

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
        categories = ['25', '26', '28']

    # Test cases to try
    if not test_cases:
        test_cases = [
            {
                'name': 'Enhanced Title-only search',
                'params': [ ('keywords', query), ('sf', 'titleonly'), ('sr', 'topics'),
                           ('sk', 't'), ('sd', 'd'), ('st', '0'), ('ch', '50'), ('t', '0') ] +
                           [('fid[]', cat) for cat in categories]
            },
            {
                'name': 'Title + Content search',
                'params': [ ('keywords', query), ('scf', '1'), ('sr', 'topics'),
                           ('sk', 't'), ('sd', 'd'), ('st', '0'), ('ch', '50') ] +
                           [('fid[]', cat) for cat in categories]
            }
        ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔬 Test {i}: {test_case['name']}")
        print("-" * 50)

        try:
            # Execute search
            response = session.get(f"{base_url}/search.php", params=test_case['params'], timeout=30, allow_redirects=True)

            if response.status_code != 200:
                print(f"❌ Failed with status {response.status_code}")
                continue

            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all potential search result links
            results = []
            count_elements = soup.find_all(['li', 'div'], class_=re.compile(r'row|bg2'))

            for element in count_elements:
                # Look for topic titles
                link = element.find('a', class_='topictitle')
                if link and link.get('href'):
                    full_text = element.get_text().strip()
                    if full_text and len(full_text) > 5:  # Filter meaningful entries
                        results.append(full_text[:150])  # Truncate long titles

            print(f"📊 Found {len(results)} total result entries")

            # Enhanced relevance filtering
            search_terms = query.lower().split()
            relevant = []
            not_relevant = []

            for result in results[:100]:  # Process first 100 results
                result_lower = result.lower()
                # Use improved matching algorithm
                if all(contains_partial_match(term, result_lower) for term in search_terms):
                    relevant.append(result)
                else:
                    not_relevant.append(result)

            print(f"   ✅ {query}-related: {len(relevant)}")
            if relevant:
                for i, title in enumerate(relevant[:5]):  # Show first 5
                    print(f"      {i+1}. {title}")

            print(f"   ❌ Not {query}-related: {len(not_relevant)}")
            if not_relevant and len(not_relevant) <= 3:
                for i, title in enumerate(not_relevant[:3]):
                    print(f"      • {title}")

        except Exception as e:
            print(f"❌ Search failed: {e}")

    print("\n" + "=" * 70)
    print("Enhanced diagnostic complete! Results above show improved relevance detection.")
    print("\n🔍 This now detects:")
    print("   ✅ 'Matrix' in 'Animatrix' (substring match)")
    print("   ✅ 'Dexter:' in 'Dexter: Resurrection' (prefix match)")
    print("   ✅ Multi-term combinations with flexible positioning")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced MirCrew Search Diagnostics')
    parser.add_argument('-q', '--query', default='Matrix', help='Search term to test')
    args = parser.parse_args()

    diagnostic_search(args.query)