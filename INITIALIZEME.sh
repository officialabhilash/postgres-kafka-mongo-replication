#!/bin/bash

# build
docker compose -f docker-compose.local.yml up -d

sleep 6
# initialize postgres with data
sudo chown -R 1000:1000 ./data/kafka
sudo chown -R 472:472 ./data/grafana

# synchronizing progress
sleep 15

./register-postgres-connector.sh
./register-mongodb-sink-connector.sh


echo "Initialization complete"
