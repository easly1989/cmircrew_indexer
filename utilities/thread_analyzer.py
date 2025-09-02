#!/usr/bin/env python3
"""
Thread Analyzer Script - Analyze PHPBB thread HTML to extract magnet titles and seed/peer info
"""

import os
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests
from urllib.parse import urljoin

# Load env vars
load_dotenv()

# Import login (temporarily)
import sys
sys.path.insert(0, os.path.dirname(__file__))
from login import MirCrewLogin

def analyze_thread_structure(query="Dexter", max_threads=3):
    """Analyze thread HTML to understand magnet title and seed/peer structure"""

    print(f"🔍 Analyzing thread structure for '{query}'")
    print("=" * 80)

    # Authenticate
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

    # First find some threads with magnets
    search_params = [
        ('keywords', query),
        ('sf', 'titleonly'),
        ('sr', 'topics'),
        ('sk', 't'),
        ('sd', 'd'),
        ('st', '0'),
        ('ch', '50'),
        ('t', '0')
    ]

    # Add categories based on query
    if 'dexter' in query.lower():
        search_params.append(('fid[]', '51'))
        search_params.append(('fid[]', '52'))
    else:
        search_params.append(('fid[]', '25'))
        search_params.append(('fid[]', '26'))

    print(f"🔍 Searching for '{query}' to find threads...")

    # Search and get thread URLs
    response = session.get(f"{base_url}/search.php", params=search_params, timeout=30)
    if response.status_code != 200:
        print(f"❌ Search failed: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    threads_analyzed = 0

    # Find thread links
    for row in soup.find_all(['li', 'div'], class_=re.compile(r'row|bg2')):
        if threads_analyzed >= max_threads:
            break

        title_link = row.find('a', class_='topictitle')
        if not title_link or not title_link.get('href'):
            continue

        thread_url = urljoin(base_url, title_link['href'])
        thread_title = title_link.get_text().strip()

        print(f"\n📄 ANALYZING THREAD {threads_analyzed + 1}: {thread_title[:80]}...")
        print(f"   URL: {thread_url}")
        print("-" * 60)

        # Fetch thread content
        thread_response = session.get(thread_url, timeout=30)
        if thread_response.status_code != 200:
            print(f"   ❌ Failed to fetch thread content")
            continue

        thread_soup = BeautifulSoup(thread_response.text, 'html.parser')

        # Look for magnet information
        magnet_count = 0

        # Find all potential magnet areas - PHPBB typically uses these patterns
        for post in thread_soup.find_all(['div'], class_=re.compile(r'postbody|post-text|content')):

            # Look for magnet links
            for magnet_link in post.find_all('a', href=re.compile(r'magnet:\?xt=urn:btih:')):
                magnet_count += 1
                magnet_url = magnet_link['href'].strip()

                print(f"   🔗 MAGNET #{magnet_count}:")
                print(f"      URL: {magnet_url[:100]}...")

                # Try to get title - it's usually right after the magnet link
                magnet_title = None

                # Method 1: Check for a span or strong right after the link
                next_elem = magnet_link.find_next(['span', 'strong', 'b', 'p', 'div'])
                if next_elem and next_elem.get_text(strip=True):
                    magnet_title = next_elem.get_text(strip=True)
                    print(f"      TITLE (next elem): '{magnet_title[:100]}'")

                # Method 2: Look for text between ], [ or in quotes after magnet
                parent = magnet_link.parent
                if parent:
                    parent_text = parent.get_text()
                    # Look for patterns after magnet
                    magnet_match = re.search(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}[^\\[]*\\[(.*?)[\\]]', parent_text)
                    if magnet_match:
                        magnet_title = magnet_match.group(1).strip()
                        print(f"      TITLE (pattern): '{magnet_title[:100]}'")

                # Try to find seed/leech information
                # Look in dl/dt/dd structures
                seed_info = None
                peer_info = None

                # Find dl elements that might contain torrent info
                for dl in post.find_all('dl'):
                    dt_text = dl.find('dt')
                    if dt_text:
                        dt_label = dt_text.get_text(strip=True).lower()
                        dd = dt_text.find_next_sibling('dd')
                        if dd:
                            dd_value = dd.get_text(strip=True)
                            if 'seed' in dt_label or 'seeder' in dt_label:
                                seed_info = dd_value
                                print(f"      SEEDS: '{seed_info}'")
                            elif 'leech' in dt_label or 'peer' in dt_label or 'down' in dt_label:
                                peer_info = dd_value
                                print(f"      LEECHS/PEERS: '{peer_info}'")

                # Look for other patterns - PHPBB torrent areas often have specific structure
                # Look for spans or divs after magnet that might contain title
                if not magnet_title:
                    # Check siblings
                    for sibling in magnet_link.parent.find_next_siblings():
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text and len(sibling_text) > 5 and len(sibling_text) < 200:
                            magnet_title = sibling_text
                            print(f"      TITLE (sibling): '{magnet_title[:100]}...'")

                # Alternative: look for text context around magnet
                if not magnet_title:
                    magnet_pos = post.get_text().find('magnet:?xt=urn')
                    if magnet_pos != -1:
                        after_magnet = post.get_text()[magnet_pos:]
                        # Look for bracketed content or quoted content after magnet
                        bracket_match = re.search(r'magnet:[^\\[]*\\[(.*?)[\\]]', after_magnet)
                        if bracket_match:
                            magnet_title = bracket_match.group(1).strip()
                            print(f"      TITLE (context): '{magnet_title[:100]}...'")

        if magnet_count == 0:
            print("   ⚠️ No magnets found in this thread")
        else:
            print(f"   ✅ Found {magnet_count} magnet(s) in thread")

        threads_analyzed += 1
        print()

    print("=" * 80)
    print("Thread analysis complete!")
    print("Key findings:")
    print("- Magnet titles are typically right after the magnet link")
    print("- Look for <dl><dt><dd> structures for seed/leech info")
    print("- PHPBB threads may use different HTML structures")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Thread Structure Analyzer')
    parser.add_argument('-q', '--query', default='Dexter', help='Query to analyze')
    parser.add_argument('-n', '--threads', type=int, default=2, help='Number of threads to analyze')
    args = parser.parse_args()

    analyze_thread_structure(args.query, args.threads)