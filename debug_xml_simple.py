#!/usr/bin/env python3
"""Simple debug script for XML parsing issues"""

# Direct execution to avoid import issues
caps_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<caps>
    <server version="1.0" title="MirCrew Indexer" strapline="MirCrew Indexer API" email="support@example.com" url="http://localhost:9118" image="http://localhost:9118/api"/>
    <limits max="100" default="50"/>
    <registration available="no" open="no"/>
    <searching>
        <search available="yes" supportedParams="q,cat,season,ep"/>
        <tv-search available="yes" supportedParams="q,cat,season,ep"/>
        <movie-search available="yes" supportedParams="q,cat"/>
    </searching>
    <categories>
        <category id="2000" name="Movies">
            <subcat id="2010" name="Movies/SD"/>
            <subcat id="2040" name="Movies/HD"/>
            <subcat id="2050" name="Movies/BluRay"/>
        </category>
        <category id="5000" name="TV">
            <subcat id="5020" name="TV/SD"/>
            <subcat id="5040" name="TV/HD"/>
            <subcat id="5050" name="TV/Other"/>
        </category>
    </categories>
</caps>'''

test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>Total results</title>
            <torznab:attr name="total" value="1"/>
        </item>
        <item>
            <title>MirCrew.Indexer.Test.Response.SAMPLE.avi</title>
            <guid>magnet-test-0</guid>
            <link>magnet:?xt=urn:btih:TEST1234567890TEST1234567890TEST12&dn=MirCrew.Indexer.Test.Response.SAMPLE.avi</link>
            <comments>https://mircrew-indexer.test/test-thread</comments>
            <pubDate>2025-09-02T14:55:57.082Z</pubDate>
            <category>Movies</category>
            <size>1000000000</size>
            <description>Magnet: MirCrew.Indexer.Test.Response.SAMPLE.avi</description>
            <torznab:attr name="category" value="25"/>
            <torznab:attr name="size" value="1000000000"/>
            <torznab:attr name="seeders" value="1"/>
            <torznab:attr name="peers" value="2"/>
            <torznab:attr name="downloadvolumefactor" value="0"/>
            <torznab:attr name="uploadvolumefactor" value="1"/>
        </item>
    </channel>
</rss>'''

print("CAPABILITIES XML:")
print("=================")
print(caps_xml)
print()

# Analyze line 11
lines = caps_xml.split('\n')
print("XML Lines Analysis:")
for i, line in enumerate(lines, 1):
    print("2d")

print()
print("SPECIFICALLY ANALYZING LINE 11:")
if len(lines) >= 11:
    line11 = lines[10]  # 0-indexed
    print(f"Line 11: {repr(line11)}")
    if len(line11) >= 76:
        char76 = line11[75]  # 0-indexed
        print(f"Character at position 76: '{char76}' (ord: {ord(char76)})")
        print(f"Context around position 76: {repr(line11[70:80])}")
    else:
        print(f"Line 11 only has {len(line11)} characters")

# Look for unescaped ampersands
print()
print("CHECKING FOR UNESCAPED AMPERSANDS:")
if '&' in caps_xml:
    print("Found unescaped ampersands:")
    for i, char in enumerate(caps_xml):
        if char == '&':
            context = caps_xml[max(0, i-10):min(len(caps_xml), i+10)]
            print(f"At position {i}: {repr(context)}")
else:
    print("No unescaped ampersands found")

# Try to parse the XML
print()
print("TESTING XML PARSING:")
try:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(caps_xml)
    print("✓ XML parsing successful!")
except Exception as e:
    print("✗ XML parsing failed:", str(e))