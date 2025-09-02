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

        return params

    def _capabilities_response(self) -> Response:
        """Return Torznab capabilities XML"""
        caps_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<caps>
    <server version="1.0" title="MirCrew Indexer" strapline="MirCrew Indexer API" email="support@mircrew-indexer.local" url="http://localhost" image="http://localhost/logo.png"/>
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
        try:
            # Build command line arguments for the indexer
            cmd_args = [sys.executable, 'mircrew_indexer.py']

            # Add query parameter
            if params.get('q'):
                cmd_args.extend(['-q', params['q']])

            # Add season/episode if provided
            if params.get('season'):
                cmd_args.extend(['-season', params['season']])

            if params.get('ep'):
                cmd_args.extend(['-ep', params['ep']])

            logger.info(f"Executing indexer with args: {cmd_args}")

            # Execute the indexer as subprocess
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
                cwd=os.path.dirname(__file__)  # Run from script directory
            )

            if result.returncode == 0:
                logger.info(f"Indexer execution successful, output length: {len(result.stdout)}")
                return Response(result.stdout, mimetype='application/xml')
            else:
                logger.error(f"Indexer execution failed: {result.stderr}")
                return self._error_response(f"Indexer execution failed: {result.stderr}", 500)

        except subprocess.TimeoutExpired:
            logger.error("Indexer execution timed out")
            return self._error_response("Indexer execution timed out", 504)
        except Exception as e:
            logger.error(f"Search execution error: {str(e)}")
            return self._error_response(f"Search execution error: {str(e)}", 500)

    def _error_response(self, message: str, code: int = 500) -> Response:
        """Return error response in Torznab format"""
        error_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<error code="{code}" description="{message}"/>'''
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

    if not os.path.exists('.env'):
        logger.warning(".env file not found - indexer may fail if credentials are required")

    # Create and run server
    server = MirCrewAPIServer()
    server.run()

if __name__ == '__main__':
    main()