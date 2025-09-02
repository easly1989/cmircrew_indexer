#!/usr/bin/env python3
"""Debug script to identify XML parsing errors"""

import sys
import os
sys.path.append('.')

# Import the API methods directly
exec(open('mircrew_api.py').read())

def debug_xml_response():
    """Debug what XML responses look like"""

    # Test capabilities response
    print("="*50)
    print("CAPABILITIES RESPONSE:")
    print("="*50)

    caps_response = MirCrewAPIServer._capabilities_response(None)
    caps_xml = str(caps_response.data, 'utf-8')

    print("Full Response:")
    print(repr(caps_xml))
    print("\nFormatted:")
    print(caps_xml)

    print("\nLine-by-line analysis:")
    lines = caps_xml.split('\n')
    for i, line in enumerate(lines, 1):
        print("5")
        if i >= 10:  # Only show first 10 lines for clarity
            print(f"    ... and {len(lines) - 10} more lines")
            break

    # Look at position 76 specifically around line 11
    if len(lines) >= 11:
        line11 = lines[10]  # 0-indexed
        if len(line11) >= 76:
            char76 = line11[75]  # 0-indexed
            print("76")
            print(f"Context around position 76: '{line11[70:80]}'")
        else:
            print("76"
    # Test test response
    print("\n" + "="*50)
    print("TEST RESPONSE:")
    print("="*50)

    test_response = MirCrewAPIServer._test_request_response(None)
    test_xml = str(test_response.data, 'utf-8')

    print("Formatted:")
    print(test_xml)

if __name__ == '__main__':
    debug_xml_response()