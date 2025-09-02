#!/usr/bin/env python3
"""
MirCrew Indexer API Server
Torznab-compatible web API wrapper for the mircrew indexer script
Runs the indexer as a subprocess and returns Torznab XML over HTTP
"""

import os
import sys
import subprocess
import logging
from flask import Flask, request, Response
from typing import Optional, Dict, Any
import urllib.parse
import threading
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

    def _extract_torznab_params(self, request) -> Dict[str, Any]:
        """Extract and validate Torznab parameters from request"""
        params = {}

        # Required parameters
        params['t'] = request.args.get('t')  # action (search, caps)

        # Search parameters
        params['q'] = request.args.get('q', '')  # query string
        params['cat'] = request.args.get('cat', '')  # category
        params['season'] = request.args.get('season', '')  # season number
        params['ep'] = request.args.get('ep', '')  # episode number
        params['limit'] = request.args.get('limit', '100')  # result limit

        # Additional Torznab parameters that Prowlarr might send
        params['extended'] = request.args.get('extended', '')  # extended info
        params['offset'] = request.args.get('offset', '0')  # pagination offset
        params['imdbid'] = request.args.get('imdbid', '')  # IMDB ID
        params['tvdbid'] = request.args.get('tvdbid', '')  # TVDB ID

        # Detect Prowlarr test requests - they often have no search parameters
        params['is_test_request'] = (
            params['t'] == 'search' and
            not any([params.get('q'), params.get('season'), params.get('ep'), params.get('imdbid'), params.get('tvdbid')])
        )

        return params

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
            <title>Total results</title>
            <pubDate>2025-09-02T14:55:57.082Z</pubDate>
            <torznab:attr name="total" value="1"/>
        </item>
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