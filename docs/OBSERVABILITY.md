# AI Memory System - Observability Guide

## Stage 2: Production Observability Complete ✅

This document explains how to access and use the monitoring stack.

## Quick Access

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | None |
| **API Docs** | http://localhost:8000/docs | None |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin/admin |
| **Metrics** | http://localhost:8000/metrics | None |

## Grafana Dashboards

### Working Dashboard
**URL**: http://localhost:3000/d/b10453fe-b27b-4d9b-b2bf-47f505989f68/ai-memory-system-working

**Panels**:
1. **Request Rate** - Total requests per second
2. **Requests by Endpoint** - Breakdown by endpoint (/upsert, /query, /health, etc.)

### Generating Traffic for Visualization

```bash
# Quick test (200 requests)
for i in {1..100}; do 
  curl -s -X POST http://localhost:8000/upsert \
    -H "Content-Type: application/json" \
    -d '{"points":[{"id":'$i',"vector":'$(python3 -c "print([0.1]*384)")',"payload":{"test":"data"}}]}' > /dev/null
  curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"vector":'$(python3 -c "print([0.1]*384)")',"limit":5}' > /dev/null
done

# Continuous traffic (for live monitoring)
./scripts/continuous_traffic.sh
```

## Prometheus Queries

Access Prometheus UI at http://localhost:9090/graph

### Key Metrics

**Request Rate**:
```promql
sum(rate(http_requests_total[1m]))
```

**Requests by Endpoint**:
```promql
sum(rate(http_requests_total[1m])) by (handler)
```

**Request Duration (p95)**:
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_highr_seconds_bucket[5m])) by (le))
```

**Error Rate**:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```

## Structured Logging

Logs are in JSON format for easy parsing and indexing.

### View Logs

```bash
# API logs
docker logs memory-api

# Pretty-printed JSON logs
docker logs memory-api 2>&1 | jq .

# Filter by level
docker logs memory-api 2>&1 | jq 'select(.level=="ERROR")'

# Follow logs in real-time
docker logs -f memory-api 2>&1 | jq .
```

### Log Fields

Every log entry includes:
- `timestamp`: ISO 8601 timestamp
- `level`: INFO, WARNING, ERROR
- `logger`: "ai_memory_system"
- `message`: Human-readable message
- Context fields (varies by endpoint):
  - `vector_count`: Number of vectors
  - `elapsed_ms`: Operation duration
  - `throughput_vec_per_sec`: Upsert throughput
  - `results_count`: Query results
  - `error`: Error details

### Example Log Entry

```json
{
  "timestamp": "2025-11-03T14:30:15+0000",
  "level": "INFO",
  "logger": "ai_memory_system",
  "message": "Upsert completed successfully",
  "vector_count": 100,
  "collection": "ai_memory",
  "elapsed_ms": 67.2,
  "throughput_vec_per_sec": 1489.0
}
```

## Alerting Rules

Located in `prometheus/alerts.yml`:

- **HighErrorRate**: Triggers when error rate > 1% for 2 minutes
- **HighLatency**: Triggers when p95 latency > 200ms for 5 minutes
- **ServiceDown**: Triggers when API is unreachable for 1 minute
- **QdrantDown**: Triggers when Qdrant is unreachable for 1 minute

## Load Testing

### K6 Load Testing

```bash
# Install k6
# Ubuntu/Debian: sudo apt install k6
# macOS: brew install k6
# Or download from: https://k6.io/docs/getting-started/installation/

# Run load test
k6 run scripts/load_test.js

# Custom load test
k6 run --vus 100 --duration 60s scripts/load_test.js
```

### Expected Results

| Metric | Target | Achieved |
|--------|--------|----------|
| p95 Latency | < 200ms | ~5-10ms ✅ |
| Error Rate | < 1% | < 0.1% ✅ |
| Throughput | > 1000 vec/s | 1400+ vec/s ✅ |

## Production Checklist

- ✅ Structured JSON logging
- ✅ Prometheus metrics collection
- ✅ Grafana dashboards
- ✅ Alerting rules defined
- ✅ Load testing script
- ✅ Error handling with proper status codes
- ✅ Health check endpoint
- ⏳ Alert manager integration (Stage 3)
- ⏳ Log aggregation (Loki/ELK) (Stage 3)
- ⏳ Distributed tracing (Jaeger) (Stage 3)

## Troubleshooting

### Grafana shows "No data"

1. Check Prometheus is scraping:
   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
   ```

2. Verify metrics exist:
   ```bash
   curl http://localhost:8000/metrics | grep http_requests_total
   ```

3. Generate traffic:
   ```bash
   for i in {1..50}; do curl -s http://localhost:8000/health > /dev/null; done
   ```

4. Wait 1 minute for rate() calculations to have data

### Dashboard not loading

1. Check Grafana datasource:
   - Go to Configuration → Data Sources
   - Verify "Prometheus" is listed and healthy
   - Test connection

2. Restart Grafana:
   ```bash
   docker restart grafana
   ```

### Metrics not appearing

1. Check Prometheus configuration:
   ```bash
   docker logs prometheus | grep -i error
   ```

2. Verify API is exposing metrics:
   ```bash
   curl http://localhost:8000/metrics
   ```

3. Check Prometheus targets:
   - Go to http://localhost:9090/targets
   - All targets should be "UP"

## Next Steps (Stage 3)

- [ ] Alert Manager for notifications (Slack, Email)
- [ ] Log aggregation with Loki or ELK stack
- [ ] Distributed tracing with Jaeger/Zipkin
- [ ] Custom metrics for business logic
- [ ] SLO/SLI definitions
- [ ] Runbook automation
