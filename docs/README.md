# MirCrew Indexer

A Torznab-compatible indexer for the MirCrew semi-private torrent forum, providing automatic authentication, scraping, magnet unlocking, and XML generation for Prowlarr integration.

## ⚠️ Important Notice

**This software is intended for users with valid MirCrew forum accounts. Ensure you have permission to access the content you're indexing.**

## Features

- 🔐 **Automatic Authentication**: Robust login with retry logic and anti-detection measures
- 🧲 **Magnet Unlocking**: Automatic "Thanks" button clicking to unlock hidden magnet links
- 🗑️ **Scraping**: Reliable HTML parsing with fallback mechanisms
- 📝 **Torznab Compatibility**: Full Torznab XML output for Prowlarr integration
- 🐳 **Docker Support**: Multi-stage Docker build with health checks
- 🧪 **Comprehensive Testing**: Unit, integration, and mock testing
- 📊 **Monitoring**: Detailed logging and health check endpoints

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Docker](#docker)
- [Development](#development)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.8+
- Access to MirCrew forum account
- Valid credentials (username/password)

### From Source

```bash
# Clone the repository
git clone https://github.com/mircrew/mircrew-indexer.git
cd mircrew-indexer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or for development
pip install -r requirements.txt -r requirements-dev.txt
```

### From PyPI

```bash
pip install mircrew-indexer
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required environment variables:

```env
# MirCrew Credentials (REQUIRED)
MIRCREW_USERNAME=your_username_here
MIRCREW_PASSWORD=your_password_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=9118
TIMEOUT=30
MAX_RESULTS=100

# Logging
LOG_LEVEL=INFO
```

### Optional Environment Variables

```env
# Logging Configuration
LOG_FILE=logs/mircrew_indexer.log
LOG_FORMAT=[%(asctime)s] %(levelname)s - %(name)s: %(message)s

# HTTP Configuration
REQUESTS_TIMEOUT=30
MAX_RETRIES=5
BACKOFF_FACTOR=2.0

# Caching (future feature)
ENABLE_CACHE=false
CACHE_SIZE_MB=100
```

## Usage

### Standalone CLI

```bash
# Basic search
mircrew-indexer -q "The Matrix"

# Direct thread search
mircrew-indexer -q "thread::180404"

# With season/episode
mircrew-indexer -q "Dexter" -season 1 -ep 1
```

### API Server

```bash
# Start the API server
mircrew-api

# The server will be available at http://localhost:9118
```

### API Endpoints

- `GET /api` - Torznab search endpoint
- `GET /download/{magnet_hash}` - Torrent download endpoint
- `GET /health` - Health check endpoint
- `GET /` - API information

### Torznab Parameters

- `t=search` - Search
- `q` - Search query
- `cat` - Category ID
- `season` - Season number
- `ep` - Episode number

### Example Torznab Search

```bash
curl "http://localhost:9118/api?t=search&q=The+Matrix&cat=2000"
```

## Docker

### Quick Start

```bash
# Build and run with docker-compose
docker-compose -f docker/docker-compose.yml up --build
```

### Manual Docker Build

```bash
# Build the image
docker build -f docker/Dockerfile.api -t mircrew-indexer .

# Run the container
docker run -p 9118:9118 \
  -e MIRCREW_USERNAME=your_username \
  -e MIRCREW_PASSWORD=your_password \
  mircrew-indexer
```

### Docker Compose Development

```bash
# Development environment
docker-compose -f docker/docker-compose.dev.yml up --build

# Check health
curl http://localhost:9118/health
```

### Environment Variables for Docker

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=9118

# MirCrew Credentials
MIRCREW_USERNAME=your_username
MIRCREW_PASSWORD=your_password

# Optional: Mount configuration
# docker run -v $(pwd)/config:/app/config ...
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Code formatting
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

### Project Structure

```
src/mircrew/
├── api/                # Flask API server
├── core/               # Core functionality
│   ├── auth.py         # Authentication
│   ├── scraper.py      # Forum scraping
│   ├── indexer.py      # XML generation
│   └── magnet_unlock.py # Magnet unlocking
├── config/             # Configuration management
├── utils/              # Utilities
└── __init__.py

tests/
├── unit/               # Unit tests
├── integration/        # Integration tests
└── fixtures/           # Test data

config/
├── mircrew.yml         # Category mappings
└── logging.yml         # Logging configuration

docker/
├── Dockerfile.api      # API server Docker
├── docker-compose.yml  # Production compose
└── docker-compose.dev.yml  # Development compose
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_auth.py

# Run with verbose output
pytest -v

# Run tests with coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report

# Run integration tests
pytest tests/integration/

# Run tests matching pattern
pytest -k "test_login"
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Check formatting
black --check src/ tests/
isort --check src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/

# All quality checks (via pre-commit)
pre-commit run --all-files
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run quality checks: `pre-commit run --all-files`
5. Run tests: `pytest`
6. Submit a pull request

### Version Control Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and commit
git add .
git commit -m "feat: add your feature"

# Run tests and checks
pytest
pre-commit run --all-files

# Push to branch
git push origin feature/your-feature
```

## API Reference

### Search Endpoint

```
GET /api?t=search&q={query}&cat={category}&season={season}&ep={episode}
```

#### Parameters

- `t`: Torznab action (search, caps)
- `q`: Search query
- `cat`: Category ID
- `season`: Season number
- `ep`: Episode number
- `year`: Release year

#### Example Request

```bash
curl "http://localhost:9118/api?t=search&q=The+Matrix&cat=2000&season=1&ep=1"
```

#### Example Response

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <item>
      <title>The Matrix (1999)</title>
      <guid>magnet-180404-0</guid>
      <link>magnet:?xt=urn:btih:...</link>
      <category>Movies</category>
      <size>1465487237</size>
      <pubDate>Wed, 21 Oct 1999 02:00:00 GMT</pubDate>
      <torznab:attr name="category" value="2000"/>
      <torznab:attr name="size" value="1465487237"/>
      <torznab:attr name="seeders" value="1"/>
      <torznab:attr name="peers" value="2"/>
    </item>
  </channel>
</rss>
```

### Direct Thread Search

Use `thread::{thread_id}` syntax for direct thread searches:

```bash
curl "http://localhost:9118/api?t=search&q=thread::180404"
```

### Capabilities Endpoint

```
GET /api?t=caps
```

Returns Torznab server capabilities.

### Torrent Download

```
GET /download/{magnet_hash}
```

Downloads a .torrent file generated from the magnet hash.

### Health Check

```
GET /health
```

Returns server health status.

```json
{
  "status": "healthy",
  "timestamp": "2025-09-03T15:00:00Z",
  "version": "1.0.0"
}
```

## Troubleshooting

### Common Issues

#### Authentication Failed
```
Error: Authentication failed - verify MIRCREW_USERNAME and MIRCREW_PASSWORD
```

**Solution:**
- Check credentials are correct in `.env`
- Ensure account is not banned/suspended
- Wait and retry (may be temporary rate limiting)

#### Search Returns No Results
```
Warning: No magnet links found - check search parameters
```

**Solution:**
- Verify search query format
- Check category mappings in `config/mircrew.yml`
- Forum may be down or changed structure

#### Docker Health Check Fails
```
Health check failed: Connection refused
```

**Solution:**
- Ensure port 9118 is not in use
- Check Docker logs: `docker logs <container>`
- Verify environment variables are set

#### Memory Issues
```
MemoryError: Out of memory
```

**Solution:**
- Increase Docker memory limit
- Reduce MAX_RESULTS in configuration
- Process fewer results per request

### Debug Logging

Enable detailed logging:

```env
LOG_LEVEL=DEBUG
LOG_FILE=logs/debug.log
```

### Network Troubleshooting

```bash
# Test connectivity
python -c "import requests; print(requests.get('https://mircrew-releases.org').status_code)"

# Check DNS resolution
nslookup mircrew-releases.org

# Test with custom timeout
curl --max-time 30 https://mircrew-releases.org
```

### Configuration Validation

```bash
# Validate .env file
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = ['MIRCREW_USERNAME', 'MIRCREW_PASSWORD', 'API_HOST', 'API_PORT']
missing = [k for k in required if not os.getenv(k)]
if missing:
    print(f'Missing required variables: {missing}')
else:
    print('Configuration looks good!')
"
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## Support

- 📖 **Documentation**: https://github.com/mircrew/mircrew-indexer#readme
- 🐛 **Issues**: https://github.com/mircrew/mircrew-indexer/issues
- 💬 **Discussions**: https://github.com/mircrew/mircrew-indexer/discussions

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for recent changes and version history.