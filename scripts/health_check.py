#!/usr/bin/env python3
"""
Health Check Script for MirCrew Indexer API

This script checks the health status of the MirCrew API service by
making a GET request to the /health endpoint and validates the response.

Exit codes:
0 - Health check passed (API is healthy)
1 - Health check failed (API returned non-healthy status)
2 - Connection error/timeout (unable to reach API)
3 - Invalid JSON response (malformed response)
"""

import sys
import requests
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
HEALTH_URL = "http://localhost:9118/health"
TIMEOUT = 5  # seconds


def check_health() -> Dict[str, Any]:
    """
    Perform health check by calling the API's /health endpoint

    Returns:
        Dict containing health status or error information

    Raises:
        requests.exceptions.RequestException: Connection-related errors
        ValueError: JSON parsing errors
    """
    try:
        logger.info(f"Checking health at {HEALTH_URL}")

        response = requests.get(HEALTH_URL, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Validate response structure
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object")

        logger.info(f"Health check response: {data}")
        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"Connection error: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        raise


def main():
    """Main health check logic with appropriate exit codes"""
    try:
        result = check_health()

        # Check if status is 'healthy'
        if result.get('status') == 'healthy':
            print("✅ Health check PASSED - API is healthy")
            # Print additional info if available
            if 'uptime' in result:
                print(f"   Uptime: {result['uptime']}")
            if 'timestamp' in result:
                print(f"   Timestamp: {result['timestamp']}")
            sys.exit(0)

        else:
            print(f"❌ Health check FAILED - API status: {result.get('status', 'unknown')}")
            sys.exit(1)

    except requests.exceptions.RequestException:
        print("❌ Health check FAILED - Cannot connect to API")
        print("   Make sure the API server is running and accessible")
        sys.exit(2)

    except ValueError:
        print("❌ Health check FAILED - Invalid response from API")
        sys.exit(3)

    except Exception as e:
        print(f"❌ Health check FAILED - Unexpected error: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main()