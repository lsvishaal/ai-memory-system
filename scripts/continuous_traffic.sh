#!/bin/bash
# Continuous traffic generator for observability demo

echo "🔄 Starting continuous traffic generation..."
echo "📊 This will generate metrics for Grafana visualization"
echo "⏹️  Press Ctrl+C to stop"
echo ""

VECTOR=$(python3 -c "import json; print(json.dumps([0.1] * 384))")
COUNTER=0

while true; do
    COUNTER=$((COUNTER + 1))
    
    # Upsert request
    curl -s -X POST http://localhost:8000/upsert \
        -H "Content-Type: application/json" \
        -d "{\"points\":[{\"id\":$RANDOM,\"vector\":$VECTOR,\"payload\":{\"text\":\"continuous test $COUNTER\"}}]}" > /dev/null
    
    # Query request
    curl -s -X POST http://localhost:8000/query \
        -H "Content-Type: application/json" \
        -d "{\"vector\":$VECTOR,\"limit\":5}" > /dev/null
    
    # Health check
    curl -s http://localhost:8000/health > /dev/null
    
    # Print progress every 10 requests
    if [ $((COUNTER % 10)) -eq 0 ]; then
        echo "✅ Generated $COUNTER request cycles (3 requests each = $((COUNTER * 3)) total)"
    fi
    
    sleep 1
done
