#!/bin/bash

# build
docker compose -f docker-compose.local.yml up -d

sleep 6 # sleep for 6 seconds for services to be healthy.

# initialize postgres with data
sudo chown -R 1000:1000 ./data/kafka
sudo chown -R 472:472 ./data/grafana

# synchronizing progress
sleep 15

./register-postgres-connector.sh

echo "Initialization complete"
