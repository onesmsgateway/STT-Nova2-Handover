#!/bin/bash
# Script to verify Groq API Key validity directly using curl
# Usage: ./debug_groq_key.sh [OPTIONAL_KEY]

echo "🔍 Groq API Diagnostic Tool"
echo "==========================="

KEY=""

# 1. Try to get key from argument
if [ ! -z "$1" ]; then
    KEY=$1
    echo "> Using key from argument"
else
    # 2. Try to get key from .env
    if [ -f .env ]; then
        echo "> Loading .env file..."
        # Extract GROQ_API_KEYS (handle quotes and spaces)
        RAW_KEYS=$(grep '^GROQ_API_KEYS=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
        if [ -z "$RAW_KEYS" ]; then
             RAW_KEYS=$(grep '^GROQ_API_KEY=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
        fi
        
        # Take the first key if comma separated
        IFS=',' read -ra ADDR <<< "$RAW_KEYS"
        KEY=$(echo "${ADDR[0]}" | xargs)
    fi
fi

if [ -z "$KEY" ]; then
    echo "❌ Error: No API Key found. Please pass it as argument:"
    echo "   ./debug_groq_key.sh gsk_xxxxxxxx"
    exit 1
fi

echo "🔑 Testing Key: ${KEY:0:10}......${KEY: -4}"

# 3. Make Curl Request
echo "📡 Sending request to https://api.groq.com/openai/v1/chat/completions..."

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "https://api.groq.com/openai/v1/chat/completions" \
     -H "Authorization: Bearer $KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "llama-3.3-70b-versatile",
       "messages": [{"role": "user", "content": "Hello! Reply 'OK' if you see this."}],
       "max_tokens": 10
     }')

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

echo "---------------------------"
if [ "$HTTP_STATUS" == "200" ]; then
    echo "✅ SUCCESS! API Key is VALID."
    echo "Response: $BODY"
else
    echo "❌ FAILED! API Key is INVALID or Quota Exceeded."
    echo "Status: $HTTP_STATUS"
    echo "Error: $BODY"
fi
echo "---------------------------"
