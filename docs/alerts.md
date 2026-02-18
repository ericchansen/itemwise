# Azure Monitor Alerts for Itemwise

## Prerequisites
- Application Insights connected (APPLICATIONINSIGHTS_CONNECTION_STRING set)
- OpenTelemetry instrumentation enabled (auto-configured in api.py)

## Recommended Alert Rules

### 1. Error Rate Alert
- **Metric**: requests/failed
- **Condition**: Count > 10 in 5 minutes
- **Severity**: 2 (Warning)
- **Action**: Email notification

### 2. Response Time Alert
- **Metric**: requests/duration
- **Condition**: Average > 5000ms in 5 minutes
- **Severity**: 2 (Warning)

### 3. Health Check Failure
- **Metric**: Custom metric from /health endpoint
- **Condition**: Status != healthy for 3 consecutive checks
- **Severity**: 1 (Error)

### 4. Database Connection Failures
- **Metric**: exceptions/count where type contains "SQLAlchemy"
- **Condition**: Count > 0 in 5 minutes
- **Severity**: 1 (Error)

## Setup via Azure CLI

Replace `<resource-group>`, `<app-insights-name>`, and `<action-group-id>` with your values.

### Create an Action Group (email notification)

```bash
az monitor action-group create \
  --resource-group <resource-group> \
  --name itemwise-alerts \
  --short-name iw-alerts \
  --action email admin admin@example.com
```

### Error Rate Alert

```bash
az monitor metrics alert create \
  --resource-group <resource-group> \
  --name "Itemwise High Error Rate" \
  --scopes /subscriptions/<sub>/resourceGroups/<rg>/providers/microsoft.insights/components/<app-insights-name> \
  --condition "count requests/failed > 10" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 2 \
  --action <action-group-id> \
  --description "Fires when more than 10 failed requests occur in 5 minutes"
```

### Response Time Alert

```bash
az monitor metrics alert create \
  --resource-group <resource-group> \
  --name "Itemwise Slow Responses" \
  --scopes /subscriptions/<sub>/resourceGroups/<rg>/providers/microsoft.insights/components/<app-insights-name> \
  --condition "avg requests/duration > 5000" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 2 \
  --action <action-group-id> \
  --description "Fires when average response time exceeds 5 seconds"
```

### Database Connection Failure Alert

```bash
az monitor scheduled-query create \
  --resource-group <resource-group> \
  --name "Itemwise DB Failures" \
  --scopes /subscriptions/<sub>/resourceGroups/<rg>/providers/microsoft.insights/components/<app-insights-name> \
  --condition "count > 0" \
  --condition-query "exceptions | where type contains 'SQLAlchemy' | summarize count() by bin(timestamp, 5m)" \
  --window-size 5m \
  --evaluation-frequency 5m \
  --severity 1 \
  --action-groups <action-group-id> \
  --description "Fires on any SQLAlchemy exception"
```

## Setup via Azure Portal

### Step 1: Navigate to Application Insights
1. Open the [Azure Portal](https://portal.azure.com)
2. Go to your Application Insights resource for Itemwise
3. Select **Alerts** from the left menu

### Step 2: Create a New Alert Rule
1. Click **+ Create** > **Alert rule**
2. The scope is pre-filled with your Application Insights resource

### Step 3: Configure Condition
1. Click **Add condition**
2. For error rate: search for "Failed requests" and set threshold > 10
3. For response time: search for "Server response time" and set threshold > 5000ms
4. Set the aggregation period to 5 minutes

### Step 4: Configure Action Group
1. Click **Add action groups** > **Create action group**
2. Name it (e.g., "itemwise-alerts")
3. Add notification type: Email/SMS/Push/Voice
4. Enter the recipient email address

### Step 5: Configure Alert Details
1. Set severity (1 = Error, 2 = Warning)
2. Name the rule descriptively
3. Click **Create alert rule**

## Structured Logging

The application outputs structured JSON logs in production (when `ENV=production`).
Each API request log includes:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO timestamp |
| `level` | Log level (INFO, WARNING, ERROR) |
| `logger` | Python logger name |
| `message` | Human-readable message |
| `request_id` | Unique request identifier |
| `method` | HTTP method |
| `endpoint` | Request path |
| `status_code` | HTTP response status |
| `duration_ms` | Request duration in milliseconds |

These fields are queryable in Azure Monitor via KQL:

```kusto
traces
| where message contains "GET /api"
| extend request_id = tostring(customDimensions.request_id)
| extend duration = todouble(customDimensions.duration_ms)
| where duration > 1000
| order by timestamp desc
```
