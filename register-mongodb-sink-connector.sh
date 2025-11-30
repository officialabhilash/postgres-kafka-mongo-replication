#!/bin/bash

# Script to register MongoDB Debezium SINK connector with Kafka Connect
# This connector reads from PostgreSQL CDC topics and writes to MongoDB

CONNECTOR_NAME="mongodb-sink-connector"
CONNECTOR_CONFIG_FILE="mongodb-sink-connector-config.json"
KAFKA_CONNECT_URL="http://localhost:8083"

echo "Registering MongoDB Debezium SINK connector..."
echo "This connector will sync PostgreSQL changes to MongoDB"

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
echo "Done! PostgreSQL changes will now be synced to MongoDB collection: test.books"

