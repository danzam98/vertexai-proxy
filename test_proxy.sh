#!/bin/bash
#
# Test script for Vertex AI Reasoning Proxy
#

set -e

PROXY_URL="http://localhost:8000"

echo "=== Testing Vertex AI Reasoning Proxy ==="
echo ""

# Test 1: Health check
echo "1. Health Check"
curl -s "${PROXY_URL}/health" | jq .
echo ""

# Test 2: Root endpoint
echo "2. Service Info"
curl -s "${PROXY_URL}/" | jq .
echo ""

# Test 3: Low reasoning
echo "3. Testing LOW reasoning"
curl -s -X POST "${PROXY_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-low",
    "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
    "max_tokens": 10
  }' | jq '.usage'
echo ""

# Test 4: Medium reasoning
echo "4. Testing MEDIUM reasoning"
curl -s -X POST "${PROXY_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-medium",
    "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
    "max_tokens": 10
  }' | jq '.usage'
echo ""

# Test 5: High reasoning
echo "5. Testing HIGH reasoning"
curl -s -X POST "${PROXY_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-high",
    "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
    "max_tokens": 10
  }' | jq '.usage'
echo ""

echo "=== All tests completed! ==="
echo "Check that reasoning_tokens differs across levels."
