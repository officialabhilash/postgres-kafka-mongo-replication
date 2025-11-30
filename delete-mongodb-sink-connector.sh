#!/bin/bash

# Script to delete MongoDB sink connector from Kafka Connect

CONNECTOR_NAME="mongodb-sink-connector"
KAFKA_CONNECT_URL="http://localhost:8083"

echo "Deleting MongoDB sink connector: ${CONNECTOR_NAME}..."

# Check if connector exists
EXISTING=$(curl -s "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}")

if [[ "$EXISTING" == *"404"* ]] || [[ "$EXISTING" == "" ]]; then
    echo "Connector ${CONNECTOR_NAME} does not exist."
fi

# Delete the connector
RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [[ "$HTTP_CODE" == "204" ]] || [[ "$HTTP_CODE" == "200" ]]; then
    echo "✓ Successfully deleted connector: ${CONNECTOR_NAME}"
    echo ""
    echo "Verifying deletion..."
    sleep 2
    CHECK=$(curl -s "${KAFKA_CONNECT_URL}/connectors/${CONNECTOR_NAME}")
    if [[ "$CHECK" == *"404"* ]] || [[ "$CHECK" == "" ]]; then
        echo "✓ Connector confirmed deleted."
    else
        echo "⚠ Warning: Connector may still exist. Response: $CHECK"
    fi
else
    echo "✗ Failed to delete connector. HTTP Code: $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo "Done!"

