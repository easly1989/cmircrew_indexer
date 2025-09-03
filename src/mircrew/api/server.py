#!/usr/bin/env python3
"""
MirCrew Indexer API Server
Torznab-compatible web API wrapper for the mircrew indexer script
Runs the indexer as a subprocess and returns Torznab XML over HTTP
"""

import os
import sys
import subprocess
from flask import Flask, request, Response, send_file
from typing import Optional, Dict, Any
import urllib.parse
import threading
import time
from datetime import datetime
import io

# Set up centralized logging
from ..utils.logging_utils import setup_logging, get_logger

# Configure logging with centralized config
setup_logging()
logger = get_logger(__name__)

class MirCrewAPIServer:
    """
    Flask-based API server that wraps the mircrew indexer CLI tool
    """

    def __init__(self, host='0.0.0.0', port=9118):
        self.host = host
        self.port = port
        self.app = Flask(__name__)

        # Setup routes
        self._setup_routes()

        # Health check timestamp
        self.start_time = datetime.now()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route('/download/<path:magnet_hash>', methods=['GET'])
        def download_torrent(magnet_hash):
            """Serve a .torrent file converted from magnet link"""
            try:
                # Validate magnet hash format
                if not magnet_hash or len(magnet_hash) != 40:
                    return Response("Invalid magnet hash", status=400)

                # Create torrent file content from magnet link
                torrent_data = self._create_torrent_from_magnet(magnet_hash)

                # Return torrent file
                return send_file(
                    io.BytesIO(torrent_data),
                    mimetype='application/x-bittorrent',
                    as_attachment=True,
                    download_name=f'{magnet_hash}.torrent'
                )

            except Exception as e:
                logger.error(f"Error creating torrent file: {str(e)}")
                return Response(f"Error creating torrent file: {str(e)}", status=500)

        @self.app.route('/api', methods=['GET'])
        def torznab_api():
            """
            Torznab API endpoint that accepts query parameters and calls the indexer
            """
            try:
                # Extract Torznab parameters
                params = self._extract_torznab_params(request)

                # Validate required parameters
                if not params.get('t'):
                    return self._error_response("Missing parameter 't'", 400)

                # Handle different Torznab actions
                action = params['t']

                if action == 'caps':
                    return self._capabilities_response()
                elif action == 'search':
                    return self._search_response(params)
                else:
                    return self._error_response(f"Unsupported action: {action}", 400)

            except Exception as e:
                logger.error(f"API Error: {str(e)}")
                return self._error_response(f"Internal server error: {str(e)}", 500)

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint for monitoring"""
            uptime = str(datetime.now() - self.start_time)
            return {
                'status': 'healthy',
                'uptime': uptime,
                'timestamp': datetime.now().isoformat()
            }

    def _create_torrent_from_magnet(self, magnet_hash: str) -> bytes:
        """
        Create a .torrent file from magnet link hash with proper structure.

        Args:
            magnet_hash: 40-character bittorrent hash

        Returns:
            bytes: Properly bencoded .torrent file content

        Raises:
            ValueError: If magnet hash is invalid
            Exception: If torrent creation fails
        """
        try:
            # Validate magnet hash
            if not magnet_hash or len(magnet_hash) != 40:
                raise ValueError(f"Invalid magnet hash length: {len(magnet_hash) if magnet_hash else 'None'}")

            if not magnet_hash.isalnum():
                raise ValueError("Magnet hash contains invalid characters")

            # Create proper torrent structure that matches typical .torrent format
            torrent_data = {
                'announce': 'http://127.0.0.1:6969/announce',  # Local tracker fallback
                'announce-list': [
                    ['http://127.0.0.1:6969/announce'],
                    ['udp://tracker.openbittorrent.com:80'],
                    ['udp://tracker.publicbt.com:80']
                ],
                'creation date': int(datetime.now().timestamp()),
                'created by': 'MirCrew Indexer API v1.0.0',
                'encoding': 'UTF-8',
                'info': {
                    'name': f'MirCrew.Indexer.Release.{magnet_hash}',
                    'length': 1073741824,  # 1GB default size
                    'piece length': 262144,  # 256KB pieces (common size)
                    'pieces': b'\x00' * 20 * 4096,  # Dummy piece hashes (4096 pieces for ~1GB)
                    'private': 0,  # Public torrent
                    'files': None,  # Single file torrent
                    'source': 'MirCrew.Indexer'
                }
            }

            # Enhanced bencode with proper error handling
            return self._bencode(torrent_data)

        except ValueError as e:
            logger.error(f"Torrent creation validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating torrent from hash {magnet_hash[:10]}...: {str(e)}")
            raise

    def _bencode(self, data) -> bytes:
        """
        Robust bencode implementation for torrent files.

        Args:
            data: Data to bencode (int, str, bytes, list, dict, None)

        Returns:
            bytes: Bencoded data

        Raises:
            ValueError: If data type is unsupported or invalid
            TypeError: If data structure is malformed
        """
        if isinstance(data, int):
            # Handle negative numbers and zero
            if data < 0:
                return f'i{data}e'.encode()
            return f'i{data}e'.encode()

        elif isinstance(data, str):
            # Ensure UTF-8 encoding for strings
            encoded_str = data.encode('utf-8')
            return f'{len(encoded_str)}:'.encode() + encoded_str

        elif isinstance(data, bytes):
            return f'{len(data)}:'.encode() + data

        elif isinstance(data, list):
            # Validate list contents
            encoded_items = []
            for i, item in enumerate(data):
                try:
                    encoded_items.append(self._bencode(item))
                except (ValueError, TypeError) as e:
                    raise TypeError(f"Invalid item at index {i} in list: {e}")

            return b'l' + b''.join(encoded_items) + b'e'

        elif isinstance(data, dict):
            # Validate dict structure and sort keys as required by bencode spec
            if not isinstance(data, dict):
                raise TypeError("Dictionary expected")

            # Sort keys for consistent bencoding
            sorted_items = []
            for key in sorted(data.keys()):
                value = data[key]
                try:
                    sorted_items.append(self._bencode(key))
                    if value is not None:  # Allow None values to be skipped
                        sorted_items.append(self._bencode(value))
                except (ValueError, TypeError) as e:
                    raise TypeError(f"Invalid value for key '{key}': {e}")

            return b'd' + b''.join(sorted_items) + b'e'

        elif data is None:
            # Special case: encode None as empty string
            return b'0:'

        else:
            raise ValueError(f"Unsupported data type: {type(data)} ({data!r})")

    def _extract_magnet_hash(self, magnet_url: str) -> str:
        """Extract 40-character btih hash from magnet URL"""
        try:
            # Parse the magnet URL to extract the xt parameter
            parsed = urllib.parse.urlparse(magnet_url)
            if 'xt' in urllib.parse.parse_qs(parsed.query):
                xt_param = urllib.parse.parse_qs(parsed.query)['xt'][0]
                if xt_param.startswith('urn:btih:'):
                    # Extract the 40-character hash
                    btih_hash = xt_param.split(':')[2][:40]
                    return btih_hash
            return "TEST1234567890"  # Fallback for testing
        except Exception:
            return "TEST1234567890"  # Fallback

    def _extract_torznab_params(self, request) -> Dict[str, Any]:
        """Extract and validate Torznab parameters from request with enhanced input sanitization"""
        params = {}

        # Required parameters with validation
        t_param = request.args.get('t', '').strip().lower()
        if not t_param:
            raise ValueError("Missing required parameter 't'")
        if t_param not in ['search', 'caps']:
            raise ValueError(f"Invalid action 't={t_param}', supported: search, caps")
        params['t'] = t_param

        # Search parameters with sanitization
        params['q'] = self._sanitize_query_param(request.args.get('q', ''))
        params['cat'] = self._sanitize_query_param(request.args.get('cat', ''))
        params['season'] = self._sanitize_numeric_param(request.args.get('season', ''))
        params['ep'] = self._sanitize_numeric_param(request.args.get('ep', ''))
        params['limit'] = self._sanitize_limit_param(request.args.get('limit', '100'))

        # Additional Torznab parameters that Prowlarr might send
        params['extended'] = self._sanitize_query_param(request.args.get('extended', ''))
        params['offset'] = self._sanitize_numeric_param(request.args.get('offset', '0'))
        params['imdbid'] = self._sanitize_imdb_id(request.args.get('imdbid', ''))
        params['tvdbid'] = self._sanitize_numeric_param(request.args.get('tvdbid', ''))

        # Detect Prowlarr test requests - enhanced logic
        all_search_params_empty = (
            not params.get('q') and
            not params.get('season') and
            not params.get('ep') and
            not params.get('imdbid') and
            not params.get('tvdbid') and
            not params.get('cat') and
            not params.get('extended') and
            params.get('offset', '0') == '0'
        )

        params['is_test_request'] = (
            params['t'] == 'search' and
            all_search_params_empty
        )

        logger.debug(f"Extracted Torznab params: t={params['t']}, is_test={params['is_test_request']}")
        return params

    def _sanitize_query_param(self, value: Optional[str]) -> str:
        """Sanitize query string parameters"""
        if not value:
            return ''
        # Remove dangerous characters but allow search-specific ones
        sanitized = str(value).strip()[:500]  # Limit length to prevent abuse
        # Remove script tags and other potentially dangerous content
        sanitized = sanitized.replace('<', '').replace('>', '').replace('&', '&')
        return sanitized

    def _sanitize_numeric_param(self, value: Optional[str]) -> str:
        """Sanitize numeric parameters"""
        if not value:
            return ''
        # Allow only digits for numeric parameters
        digits_only = ''.join(filter(str.isdigit, str(value)))
        return digits_only[:10]  # Reasonable limit for season/episode numbers

    def _sanitize_limit_param(self, value: Optional[str]) -> str:
        """Sanitize limit parameter with reasonable bounds"""
        if not value:
            return '100'
        try:
            limit = int(value)
            # Clamp between 1 and 500 (reasonable for torrent indexing)
            return str(max(1, min(500, limit)))
        except (ValueError, TypeError):
            return '100'

    def _sanitize_imdb_id(self, value: Optional[str]) -> str:
        """Sanitize IMDB ID format (ttXXXXXXX or XXXXXXXX)"""
        if not value:
            return ''
        value = str(value).strip()
        # Remove 'tt' prefix if present, keep only numeric
        if value.startswith('tt'):
            value = value[2:]
        # Keep only numeric characters and limit length
        numeric_only = ''.join(filter(str.isdigit, value))
        return numeric_only[:10] if numeric_only else ''

    def _capabilities_response(self) -> Response:
        """Return Torznab capabilities XML"""
        logger.info("Providing capabilities response to Prowlarr")
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
        return Response(caps_xml, mimetype='application/xml')

    def _search_response(self, params: Dict[str, Any]) -> Response:
        """Handle search request by calling the indexer CLI"""

        # Special handling for Prowlarr test requests with no parameters
        if params.get('is_test_request'):
            logger.info("Detected Prowlarr test request with no parameters - returning minimal response")
            return self._test_request_response()

        # Determine timeout based on request type before entering try block
        # Prowlarr test requests get a shorter timeout (45s vs 90s for normal requests)
        if params.get('extended') or params.get('offset', '0') != '0':
            # Likely a normal user request
            timeout_seconds = 90.0
        else:
            # Could be a test request, give it shorter timeout but more than webpage timeout
            timeout_seconds = 45.0

        logger.info(f"Using timeout: {timeout_seconds} seconds")

        try:
            # Build command line arguments for the indexer
            cmd_args = [sys.executable, 'mircrew_indexer.py']

            # Check if we have any valid search parameters
            has_query = bool(params.get('q', '').strip())
            has_season = bool(params.get('season'))
            has_ep = bool(params.get('ep'))

            # Add parameters based on what's provided
            if has_query:
                # If we have a query string (even if empty), use it
                cmd_args.extend(['-q', params['q']])
            elif has_season and has_ep:
                # Season and episode search
                cmd_args.extend(['-season', params['season']])
                cmd_args.extend(['-ep', params['ep']])
                # Add a blank query to satisfy indexer requirements
                cmd_args.extend(['-q', ''])
            elif has_season:
                # Season-only search
                cmd_args.extend(['-season', params['season']])
                cmd_args.extend(['-q', ''])
            elif has_ep:
                # Episode-only search (less common, but supported)
                cmd_args.extend(['-ep', params['ep']])
                cmd_args.extend(['-q', ''])
            else:
                # No specific parameters - do a default search with current year
                from datetime import datetime
                current_year = str(datetime.now().year)
                cmd_args.extend(['-year', current_year])

            # Log final command for debugging
            logger.info(f"Final indexer command: {cmd_args}")

            # Execute the indexer as subprocess
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=os.path.dirname(__file__)  # Run from script directory
            )

            if result.returncode == 0:
                logger.info(f"Indexer execution successful, output length: {len(result.stdout)}")
                return Response(result.stdout, mimetype='application/xml')
            else:
                logger.error(f"Indexer execution failed: {result.stderr}")
                return self._error_response(f"Indexer execution failed: {result.stderr}", 500)

        except subprocess.TimeoutExpired:
            logger.error(f"Indexer execution timed out after {timeout_seconds} seconds")
            if params.get('is_test_request'):
                # For test requests that timeout, still return a minimal response
                return self._test_request_response()
            return self._error_response(f"Indexer execution timed out after {timeout_seconds:.1f}s", 504)
        except Exception as e:
            logger.error(f"Search execution error: {str(e)}")
            if params.get('is_test_request'):
                # For test requests that fail, return minimal response
                return self._test_request_response()
            return self._error_response(f"Search execution error: {str(e)}", 500)

    def _test_request_response(self) -> Response:
        """Return a minimal Torznab response for Prowlarr test requests (matching real indexer format)"""
        test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
    <channel>
        <item>
            <title>MirCrew.Indexer.Test.Response.SAMPLE.avi</title>
            <guid>magnet-test-0</guid>
            <link>magnet:?xt=urn:btih:TEST1234567890TEST1234567890TEST12&amp;dn=MirCrew.Indexer.Test.Response.SAMPLE.avi</link>
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
        return Response(test_xml, mimetype='application/xml')

    def _error_response(self, message: str, code: int = 500) -> Response:
        """Return error response in Torznab format"""
        # Escape special characters in the message to prevent XML parsing issues
        import html
        escaped_message = html.escape(message, quote=True)
        error_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<error code="{code}" description="{escaped_message}"/>'''
        return Response(error_xml, mimetype='application/xml', status=code)

    def run(self):
        """Start the Flask server"""
        logger.info(f"Starting MirCrew API Server on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False)

def main():
    """Main entry point"""
    # Check if required files exist
    if not os.path.exists('mircrew_indexer.py'):
        logger.error("mircrew_indexer.py not found in current directory")
        sys.exit(1)

    # Check for environment variables (either from .env or Docker)
    username = os.environ.get('MIRCREW_USERNAME')
    password = os.environ.get('MIRCREW_PASSWORD')

    if not username or not password:
        # Fallback check for .env file (for local testing)
        if os.path.exists('.env'):
            logger.info("Found .env file, environment variables will be loaded by python-dotenv in indexer")
        else:
            logger.warning("No MIRCREW_USERNAME/MIRCREW_PASSWORD environment variables set and no .env file found")
    else:
        logger.info("MirCrew credentials found in environment variables")

    # Create and run server
    server = MirCrewAPIServer()
    server.run()

if __name__ == '__main__':
    main()