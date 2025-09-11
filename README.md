# GrandmaHelper Status Page

A comprehensive status monitoring system for GrandmaHelper services, similar to status.anthropic.com.

## Features

- 🟢 **Real-time monitoring** of all GrandmaHelper services
- ⏰ **Automated checks** every 30 minutes
- 🔄 **Manual refresh** button for on-demand updates
- 📊 **24-hour uptime tracking** for each service
- 🚨 **Incident tracking** and history
- 📱 **Mobile-responsive** design
- 🔌 **JSON API** for programmatic access

## Monitored Services

1. **LINE Support API** - Main assistant API
2. **Morning Image API** - Image generation service
3. **Cloud SQL Database** - PostgreSQL database
4. **Gemini AI** - Vertex AI language model
5. **Google Custom Search** - Search functionality
6. **Cloud Run Platform** - Hosting infrastructure

## Status Types

- 🟢 **Operational** - Service working normally
- 🟡 **Degraded** - Service working with issues
- 🔴 **Outage** - Service not working
- 🔵 **Maintenance** - Planned maintenance
- ⚫ **Unknown** - Status cannot be determined

## Environment Variables

Required for deployment:

```bash
# Database connection
DB_USER=postgres
DB_PASS=your-password
DB_NAME=postgres
INSTANCE_CONNECTION_NAME=hackathon-468512:asia-east1:croissant

# Optional: Morning Image API URL
MORNING_API_URL=https://your-morning-api-url

# Cloud Run
PORT=8080
```

## Deployment

### Local Development

```bash
pip install -r requirements.txt
export DB_USER=postgres
export DB_PASS=your-password
export DB_NAME=postgres
export INSTANCE_CONNECTION_NAME=hackathon-468512:asia-east1:croissant
python app.py
```

### Cloud Run Deployment

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/hackathon-468512/status-page
gcloud run deploy status-page \
  --image gcr.io/hackathon-468512/status-page \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars="DB_USER=postgres,DB_PASS=your-password,DB_NAME=postgres,INSTANCE_CONNECTION_NAME=hackathon-468512:asia-east1:croissant"
```

## API Endpoints

### GET `/`
Main status page (HTML)

### GET `/api/status`
JSON status data
```json
{
  "overall_status": "operational",
  "services": {
    "line_support_api": {
      "name": "LINE Support API",
      "status": "operational",
      "response_time": 156.7,
      "last_checked": "2025-01-11 12:30:00 UTC",
      "uptime_24h": 99.2
    }
  },
  "incidents": [],
  "last_updated": "2025-01-11 12:30:00 UTC"
}
```

### POST `/api/update`
Manual status update trigger
```json
{
  "service": "line_support_api"  // Optional: update specific service
}
```

### GET `/health`
Health check for the status page itself

## Monitoring Schedule

- **Automated checks**: Every 30 minutes
- **Manual updates**: On-demand via "Update Status" button
- **Auto-refresh**: Page refreshes every 30 seconds
- **Incident retention**: Last 10 incidents stored

## Cost Estimate

Approximately **$10-15/month** for:
- Cloud Run hosting (~$2-3/month)
- API calls to monitored services (~$8-12/month)
- Database connection tests (minimal)

## Customization

### Adding New Services

1. Add service to `StatusMonitor.__init__()`:
```python
'new_service': ServiceStatus('New Service', 'unknown', None, 'Never')
```

2. Create test function:
```python
def test_new_service(self) -> tuple[str, float]:
    # Implementation here
    pass
```

3. Add to test_functions mapping in `check_service()`

### Changing Check Intervals

Modify the schedule in `setup_background_scheduler()`:
```python
schedule.every(60).minutes.do(self.check_all_services)  # 1 hour
schedule.every().hour.do(self.check_all_services)       # Every hour
```

## Troubleshooting

**Services showing as "Unknown"**: Check environment variables and network connectivity.

**Database connection fails**: Verify Cloud SQL instance is running and connection string is correct.

**High response times**: Consider increasing timeout values in test functions.

**Status page won't start**: Check Docker logs and ensure all dependencies are installed.