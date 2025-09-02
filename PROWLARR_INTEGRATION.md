# MirCrew Indexer + Prowlarr Integration Guide

This guide explains how to integrate the MirCrew Indexer with Prowlarr running in Docker without rebuilding the Prowlarr container.

## 📋 Overview

The integration works by:

1. **API Wrapper**: Converts the CLI indexer into a Torznab-compatible web API
2. **Docker Container**: Runs the API service in the same network as Prowlarr
3. **Prowlarr Configuration**: Adds the custom indexer to Prowlarr
4. **Network Connectivity**: Both services communicate over the Docker network

## 🏗️ Architecture

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│    Prowlarr     │◄──┤  MirCrew API    │◄──┤ MirCrew Indexer │
│   (Docker)      │   │  (Docker)       │   │   (Python)      │
│                 │   │                 │   │                 │
│ • Web UI        │   │ • Flask Server  │   │ • CLI Script    │
│ • Torznab Client│   │ • Torznab API   │   │ • Magnet Links  │
│ • Radarr/Sonarr │   │ • Process Runner│   │ • Auth/Scraping │
└─────────────────┘   └─────────────────┘   └─────────────────┘
                                           ▲
                                           │
                                      ┌─────────────────┐
                                      │ mircrew-releases │
                                      │     .org        │
                                      └─────────────────┘
```

## 🚀 Quick Start

### 1. Edit Docker Compose with Your Credentials

Open `docker-compose.prowlarr.yml` and replace the placeholder values with your actual MirCrew credentials:

```yaml
environment:
  - PYTHONUNBUFFERED=1
  # MirCrew credentials - REPLACE with your actual values
  - MIRCREW_USERNAME=your_actual_username_here
  - MIRCREW_PASSWORD=your_actual_password_here
```

### 2. Start the MirCrew API Container

From your project directory:

```bash
docker-compose -f docker-compose.prowlarr.yml up -d
```

Or manually build and run:

```bash
# Build the image
docker build -f Dockerfile.api -t mircrew-api .

# Run the container
docker run -d \
  --name mircrew-indexer-api \
  --network saltbox \
  -p 9118:9118 \
  -e MIRCREW_USERNAME=your_actual_username \
  -e MIRCREW_PASSWORD=your_actual_password \
  mircrew-api
```

### 3. Test the API

```bash
# Check if API is healthy
curl http://localhost:9118/health

# Test API with a search
curl "http://localhost:9118/api?t=search&q=dexter"
```

### 4. Configure Prowlarr

1. **Access Prowlarr Web UI**
   - Go to your Prowlarr instance

2. **Add Custom Indexer**
   - Go to `Settings` → `Indexers`
   - Click `+ Add Indexer`
   - Select `Torznab (Custom)`

3. **Configure the Indexer**
   ```
   Name: MirCrew Indexer
   URL: http://mircrew-indexer-api:9118/api  # Use container name for network comms
   API Key: (leave blank - no authentication required)
   Categories: Movies (2000), TV (5000)
   ```

4. **Test the Connection**
   - Click "Test" to verify the indexer works
   - You should see successful connection and capabilities

## 🔧 Configuration Options

### Docker Compose (Recommended)

The provided `docker-compose.prowlarr.yml` includes:

- **Network Integration**: Uses your existing `saltbox` network
- **Port Exposure**: Exposes API on host port 9118
- **Direct Environment Variables**: Credentials defined directly in compose file
- **Health Checks**: Automatic monitoring and restart
- **Logging**: JSON logging with rotation

### Environment Variables

Create your environment file with:

```env
MIRCREW_USERNAME=your_actual_username
MIRCREW_PASSWORD=your_actual_password
```

### Prowlarr Settings

**Basic Configuration:**
- **Indexer Name**: `MirCrew Indexer`
- **API URL**: `http://mircrew-indexer-api:9118/api`
- **Categories**: Enable Movies (2000) and TV (5000)

**Advanced Settings:**
- **Download Factor**: `0` (free)
- **Upload Factor**: `1` (normal)
- **Priority**: Set to your preference
- **Tags**: Add any organizational tags

## 🔍 Testing the Integration

### 1. Indexer Health Check

```bash
# Test API directly
curl -s http://localhost:9118/health | jq '.status'
```

### 2. Torznab Capabilities

```bash
# Check what the indexer supports
curl "http://localhost:9118/api?t=caps"
```

### 3. Test Search Through Prowlarr

1. **Manual Search** in Prowlarr:
   - Go to `Indexers` → `Test`
   - Run a test search
   - Verify results appear

2. **Manual Search via API**:
   ```bash
   # TV Show search
   curl "http://localhost:9118/api?t=search&q=dexter%20resurrection"

   # Movie search
   curl "http://localhost:9118/api?t=search&q=matrix"
   ```

### 4. Integration Test

1. Create a test request through Radarr/Sonarr → Prowlarr → MirCrew API
2. Verify magazines are found and magnet links are returned
3. Check logs for any errors

## 📊 Monitoring and Troubleshooting

### Container Logs

```bash
# View API container logs
docker logs mircrew-indexer-api

# Follow logs in real-time
docker logs -f mircrew-indexer-api
```

### API Health Check

```bash
# Quick health check script
#!/bin/bash
if curl -s http://localhost:9118/health | grep -q "healthy"; then
    echo "✅ API is healthy"
else
    echo "❌ API is not responding"
fi
```

### Common Issues

#### ❌ "Connection failed" in Prowlarr

**Cause**: Network connectivity issue
**Solutions**:
1. Verify both containers are on the same network
2. Check container names and DNS resolution
3. Try using IP address instead of container name

```bash
# Find container IP
docker inspect mircrew-indexer-api | grep IPAddress
```

#### ❌ "Authentication failed" in API logs

**Cause**: Missing or invalid credentials
**Solutions**:
1. Check environment variables are set correctly in docker-compose.yml
2. Verify credentials are your actual MirCrew login details
3. Validate the environment variable names match exactly: `MIRCREW_USERNAME` and `MIRCREW_PASSWORD`

```bash
# Check environment variables in container
docker exec mircrew-indexer-api env | grep MIRCREW
```

#### ❌ API returns empty results

**Cause**: Indexer execution issues
**Solutions**:
1. Test indexer manually outside container
2. Check for Python dependencies
3. Verify mircrew-releases.org is accessible

```bash
# Test indexer manually
docker exec mircrew-indexer-api python mircrew_indexer.py -q "test query"
```

## 🔄 Update Process

When updating the indexer:

### 1. Stop the Current Container

```bash
docker-compose -f docker-compose.prowlarr.yml down
# OR
docker stop mircrew-indexer-api
```

### 2. Rebuild the Image

```bash
# If using docker-compose
docker-compose -f docker-compose.prowlarr.yml build --no-cache

# OR manually
docker build -f Dockerfile.api -t mircrew-api .
```

### 3. Restart the Service

```bash
docker-compose -f docker-compose.prowlarr.yml up -d
# OR
docker run [same args as before but with new image]
```

### 4. Verify in Prowlarr

- Go to Prowlarr → Settings → Indexers
- Click "Test" on the MirCrew indexer
- Ensure the test passes

## 🔧 Alternative Deployment Options

### Option 1: Portainer Stack

Use the provided `docker-compose.prowlarr.yml` as a Portainer stack:

1. **Access Portainer**
   - Go to your Portainer instance

2. **Create New Stack**
   - Name: `mircrew-indexer`
   - Upload the `docker-compose.prowlarr.yml` file
   - Deploy the stack

3. **Environment Setup**
   - Mount your `.env` file through Portainer volumes

### Option 2: Standalone Docker Run

If you prefer manual Docker commands:

```bash
# Build
docker build -f Dockerfile.api -t mircrew-api .

# Find Prowlarr container network
PROWLARR_NETWORK=$(docker inspect prowlarr | jq -r '.[0].NetworkSettings.Networks | keys[0]')

# Run with network discovery
docker run -d \
  --name mircrew-indexer-api \
  --network $PROWLARR_NETWORK \
  -p 9118:9118 \
  -v $(pwd)/your_mircrew_env.env:/app/.env:ro \
  mircrew-api
```

### Option 3: Different Port

If port 9118 conflicts:

```yaml
# In docker-compose.prowlarr.yml
services:
  mircrew-api:
    ports:
      - "9119:9118"  # Host:Container
```

Then update Prowlarr with the new host port.

### Option 4: Manual Environment Setup

If you prefer managing credentials in a .env file instead:

```yaml
# Add to docker-compose.prowlarr.yml (alternative to environment block)
services:
  mircrew-api:
    env_file:
      - your_mircrew.env
```

Then create the file with your credentials:
```env
MIRCREW_USERNAME=your_actual_username
MIRCREW_PASSWORD=your_actual_password
```

## 📈 Performance Optimization

### Container Resources

Add resource limits to `docker-compose.prowlarr.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### Indexer Caching (Future Enhancement)

Consider implementing:
- Result caching (Redis/external cache)
- Request rate limiting
- Session persistence across requests

## 🔐 Security Considerations

- **Credential Storage**: Environment variables are stored directly in docker-compose.yml
- **Network Security**: Services communicate over Docker internal network only
- **API Security**: No authentication required (internal network assumption)
- **Container User**: Runs as non-root user for additional security
- **Resource Limits**: Prevent resource exhaustion by other services
- **Git Safety**: Only commit docker-compose.yml without actual credentials

## 🎯 Search Syntax Examples

### Prowlarr/Radarr/Sonarr Usage

**TV Shows:**
- `dexter resurrection s01e01` - Specific episode
- `the office s09` - Season search
- `game of thrones` - Series search

**Movies:**
- `the matrix 1999` - Movie with year
- `interstellar extended` - Movie with additional keywords

**Direct Thread Search:**
- `thread::180404` - Search specific forum thread

### API Direct Calls

```bash
# Episode search
curl "http://localhost:9118/api?t=search&q=dexter+resurrection&season=1&ep=1"

# General search
curl "http://localhost:9118/api?t=search&q=breaking+bad"

# Thread search
curl "http://localhost:9118/api?t=search&q=thread::180404"
```

## 📝 Logs and Debugging

### API Logs

Monitor the API server logs for indexer activity:

```bash
# Real-time log monitoring
docker logs -f mircrew-indexer-api

# Last 100 lines
docker logs --tail 100 mircrew-indexer-api

# With timestamps
docker logs --timestamps mircrew-indexer-api
```

### Debug Mode

Enable debug logging by modifying the API:

```python
# In mircrew_api.py
logging.basicConfig(level=logging.DEBUG, ...)
```

### Indexer Diagnostics

Test indexer functionality inside the container:

```bash
# Access container shell
docker exec -it mircrew-indexer-api bash

# Test login
python login.py

# Test magnet unlocking
python magnet_unlock_script.py

# Test indexer
python mircrew_indexer.py -q "test query"

# Exit container
exit
```

## 🔗 Useful Links

- **Prowlarr Documentation**: [wiki.servarr.com/prowlarr](https://wiki.servarr.com/prowlarr)
- **Torznab Specification**: [torznab.github.io](https://torznab.github.io)
- **MirCrew Releases**: [mircrew-releases.org](https://mircrew-releases.org)
- **Saltbox Setup**: [github.com/saltyorg/Saltbox](https://github.com/saltyorg/Saltbox)

---

## ✅ Success Checklist

- [ ] API container is running and healthy
- [ ] Environment credentials are properly mounted
- [ ] API responds to health checks
- [ ] Prowlarr can connect to the API endpoint
- [ ] Test search returns results
- [ ] Radarr/Sonarr can use the indexer through Prowlarr
- [ ] Monitor logs for any errors
- [ ] Integration is stable and reliable

After completing this integration, you'll have a fully functional MirCrew indexer accessible through Prowlarr without modifying the Prowlarr Docker container! 🎉