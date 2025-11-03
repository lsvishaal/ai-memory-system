/**
 * K6 Load Testing Script for AI Memory System
 * 
 * This script tests the performance of the vector operations API
 * under various load conditions.
 * 
 * Usage:
 *   k6 run scripts/load_test.js                    # Default: 10 VUs for 30s
 *   k6 run --vus 50 --duration 60s scripts/load_test.js
 *   k6 run --stage 10s:10,30s:50,10s:0 scripts/load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const upsertErrors = new Counter('upsert_errors');
const queryErrors = new Counter('query_errors');
const upsertDuration = new Trend('upsert_duration');
const queryDuration = new Trend('query_duration');
const upsertSuccessRate = new Rate('upsert_success');
const querySuccessRate = new Rate('query_success');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const VECTOR_SIZE = 384;

// Load test options
export const options = {
  stages: [
    { duration: '10s', target: 10 },  // Ramp-up to 10 users
    { duration: '30s', target: 10 },  // Stay at 10 users
    { duration: '10s', target: 50 },  // Ramp-up to 50 users
    { duration: '20s', target: 50 },  // Stay at 50 users
    { duration: '10s', target: 0 },   // Ramp-down to 0
  ],
  thresholds: {
    'http_req_duration': ['p(95)<200'], // 95% of requests must complete below 200ms
    'http_req_failed': ['rate<0.01'],   // Error rate must be below 1%
    'upsert_success': ['rate>0.99'],    // Upsert success rate must be above 99%
    'query_success': ['rate>0.99'],     // Query success rate must be above 99%
    'upsert_duration': ['p(95)<150'],   // 95% of upserts below 150ms
    'query_duration': ['p(95)<100'],    // 95% of queries below 100ms
  },
};

// Helper function to generate a random vector
function generateVector() {
  const vector = [];
  for (let i = 0; i < VECTOR_SIZE; i++) {
    vector.push(Math.random() * 2 - 1); // Random values between -1 and 1
  }
  return vector;
}

// Helper function to generate unique ID
function generateId() {
  return Math.floor(Math.random() * 100000);
}

// Main test scenario
export default function () {
  const headers = { 'Content-Type': 'application/json' };
  
  // Test 1: Health check
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health check status is 200': (r) => r.status === 200,
    'health check has qdrant status': (r) => JSON.parse(r.body).qdrant !== undefined,
  });
  
  // Test 2: Upsert vectors (batch of 10)
  const upsertPayload = {
    points: []
  };
  
  for (let i = 0; i < 10; i++) {
    upsertPayload.points.push({
      id: generateId(),
      vector: generateVector(),
      payload: {
        text: `Load test document ${generateId()}`,
        category: 'load-test',
        timestamp: new Date().toISOString(),
        iteration: __ITER,
        vu: __VU,
      }
    });
  }
  
  const upsertRes = http.post(
    `${BASE_URL}/upsert`,
    JSON.stringify(upsertPayload),
    { headers }
  );
  
  const upsertSuccess = check(upsertRes, {
    'upsert status is 200': (r) => r.status === 200,
    'upsert returns success': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.status === 'success';
      } catch (e) {
        return false;
      }
    },
    'upsert duration < 200ms': (r) => r.timings.duration < 200,
  });
  
  upsertSuccessRate.add(upsertSuccess);
  if (upsertRes.status === 200) {
    upsertDuration.add(upsertRes.timings.duration);
  } else {
    upsertErrors.add(1);
    console.error(`Upsert failed: ${upsertRes.status} - ${upsertRes.body}`);
  }
  
  sleep(0.1); // Small delay between operations
  
  // Test 3: Query vectors
  const queryPayload = {
    vector: generateVector(),
    limit: 5,
    score_threshold: 0.5
  };
  
  const queryRes = http.post(
    `${BASE_URL}/query`,
    JSON.stringify(queryPayload),
    { headers }
  );
  
  const querySuccess = check(queryRes, {
    'query status is 200': (r) => r.status === 200,
    'query returns array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body);
      } catch (e) {
        return false;
      }
    },
    'query duration < 150ms': (r) => r.timings.duration < 150,
  });
  
  querySuccessRate.add(querySuccess);
  if (queryRes.status === 200) {
    queryDuration.add(queryRes.timings.duration);
  } else {
    queryErrors.add(1);
    console.error(`Query failed: ${queryRes.status} - ${queryRes.body}`);
  }
  
  sleep(0.5); // Wait before next iteration
}

// Setup function (runs once before load test)
export function setup() {
  console.log('🚀 Starting AI Memory System load test...');
  console.log(`📍 Target: ${BASE_URL}`);
  console.log(`📊 Vector size: ${VECTOR_SIZE}`);
  
  // Verify service is up
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Service is not healthy: ${res.status}`);
  }
  
  console.log('✅ Service is healthy, starting load test');
  return {};
}

// Teardown function (runs once after load test)
export function teardown(data) {
  console.log('🏁 Load test completed');
}
