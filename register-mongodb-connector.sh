#!/bin/bash

# Script to register MongoDB Debezium connector with Kafka Connect

CONNECTOR_NAME="mongodb-connector"
CONNECTOR_CONFIG_FILE="mongodb-connector-config.json"
KAFKA_CONNECT_URL="http://localhost:8083"

echo "Registering MongoDB Debezium connector..."

# Check if connector already exists
EXISTING=$(curl -s "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}")

if [[ "$EXISTING" != *"404"* ]] && [[ "$EXISTING" != "" ]]; then
    echo "Connector ${CONNECTOR_NAME} already exists. Updating..."
    curl -X PUT "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}/config" \
        -H "Content-Type: application/json" \
        -d @"${CONNECTOR_CONFIG_FILE}"
else
    echo "Creating new connector ${CONNECTOR_NAME}..."
    curl -X POST "${KAFKA_CONNECT_URL}/connectors" \
        -H "Content-Type: application/json" \
        -d @"${CONNECTOR_CONFIG_FILE}"
fi

echo ""
echo "Checking connector status..."
sleep 2
curl -s "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}/status" | python3 -m json.tool 2>/dev/null || curl -s "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}/status"

echo ""
echo "Done! Check Kafka topics for: mongodb_server.test.books"

