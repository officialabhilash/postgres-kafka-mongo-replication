# PostgreSQL CDC Setup with Kafka Connect

## Overview
This guide explains how to integrate PostgreSQL with Kafka Connect using Debezium for Change Data Capture (CDC).

## Prerequisites
✅ PostgreSQL with logical replication enabled  
✅ Publication `cdc_publication` created  
✅ Replication slot `books_cdc_slot` created  
✅ Kafka and Kafka Connect running  

## JAR Files Location

### Good News: JAR Files Are Already Included!
The `debezium/connect:3.0.0.Final` Docker image **already includes** all Debezium connectors, including:
- PostgreSQL Connector
- MongoDB Connector  
- MySQL Connector
- And more...

**You don't need to download JAR files separately!**

### If You Need JAR Files Separately
If you want to download JAR files manually (for custom setups), you can get them from:

1. **Maven Central Repository:**
   ```
   https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/
   ```

2. **Debezium Releases:**
   ```
   https://debezium.io/releases/
   ```

3. **Direct Download (PostgreSQL Connector 3.0.0.Final):**
   ```bash
   wget https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/3.0.0.Final/debezium-connector-postgres-3.0.0.Final-plugin.tar.gz
   ```

## Registering the Connector

### Method 1: Using the Script (Recommended)
```bash
./register-postgres-connector.sh
```

### Method 2: Using curl directly
```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @postgres-connector-config.json
```

### Method 3: Using Kafka UI
1. Open http://localhost:8080
2. Go to "Connectors" section
3. Click "Add Connector"
4. Paste the JSON from `postgres-connector-config.json`

## Verifying the Setup

### Check Connector Status
```bash
curl http://localhost:8083/connectors/postgres-connector/status
```

### Check Kafka Topics
```bash
# List topics
docker exec kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Should see: postgresql_server.public.books
```

### Consume Messages
```bash
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic postgresql_server.public.books \
  --from-beginning
```

## Testing CDC

1. **Insert a record in PostgreSQL:**
   ```sql
   INSERT INTO books (title, pages) VALUES ('Test Book', 100);
   ```

2. **Check Kafka topic** - you should see the change event

3. **Update a record:**
   ```sql
   UPDATE books SET pages = 200 WHERE id = 1;
   ```

4. **Delete a record:**
   ```sql
   DELETE FROM books WHERE id = 1;
   ```

## Troubleshooting

### Connector Not Starting
- Check logs: `docker logs kafka-connect`
- Verify PostgreSQL is accessible from Connect container
- Ensure publication and slot exist

### No Messages in Kafka
- Verify connector is running: `curl http://localhost:8083/connectors/postgres-connector/status`
- Check PostgreSQL WAL level: `SHOW wal_level;` (should be 'logical')
- Verify publication: `SELECT * FROM pg_publication;`

### Permission Issues
- Ensure `cdc_user` has REPLICATION privilege
- Check replication slot exists: `SELECT * FROM pg_replication_slots;`

## Configuration Details

The connector configuration uses:
- **Publication**: `cdc_publication` (pre-created)
- **Replication Slot**: `books_cdc_slot` (pre-created)
- **Plugin**: `pgoutput` (PostgreSQL's native logical replication)
- **Topic Naming**: `{database.server.name}.{schema}.{table}` = `postgresql_server.public.books`

## MongoDB Sink Connector Setup

### Overview
The MongoDB **SINK** connector reads change events from PostgreSQL CDC topics and writes them to MongoDB. This creates a real-time sync from PostgreSQL to MongoDB.

**Data Flow:**
```
PostgreSQL → (PostgreSQL Source Connector) → Kafka Topic → (MongoDB Sink Connector) → MongoDB
```

### Prerequisites
✅ PostgreSQL source connector running and capturing changes  
✅ MongoDB with replica set initialized (rs0)  
✅ MongoDB authentication configured  
✅ Kafka and Kafka Connect running  

### Registering MongoDB Sink Connector

#### Method 1: Using the Script (Recommended)
```bash
./register-mongodb-sink-connector.sh
```

#### Method 2: Using curl directly
```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @mongodb-sink-connector-config.json
```

#### Method 3: Using Kafka UI
1. Open http://localhost:8080
2. Go to "Connectors" section
3. Click "Add Connector"
4. Paste the JSON from `mongodb-sink-connector-config.json`

### Verifying MongoDB Sink Connector

#### Check Connector Status
```bash
curl http://localhost:8083/connectors/mongodb-sink-connector/status
```

#### Check Kafka Topics
```bash
# List topics
docker exec kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Should see: postgresql_server.public.books (source topic)
```

### Testing the Complete Pipeline

1. **Insert a record in PostgreSQL:**
   ```sql
   INSERT INTO books (title, pages) VALUES ('Test Book', 100);
   ```

2. **Check MongoDB** - the document should appear:
   ```javascript
   db.books.find().pretty()
   ```

3. **Update a record in PostgreSQL:**
   ```sql
   UPDATE books SET pages = 200 WHERE id = 1;
   ```

4. **Check MongoDB** - the document should be updated

5. **Delete a record in PostgreSQL:**
   ```sql
   DELETE FROM books WHERE id = 1;
   ```

6. **Check MongoDB** - the document should be deleted

### MongoDB Sink Configuration Details

The sink connector configuration:
- **Source Topic**: `postgresql_server.public.books` (from PostgreSQL CDC)
- **MongoDB Connection**: `mongodb://admin:root@mongodb:27017/?replicaSet=rs0&authSource=admin`
- **Target Database**: `test`
- **Target Collection**: `books`
- **Document ID Strategy**: Uses `id` field from PostgreSQL as MongoDB document `_id`
- **Write Strategy**: Replace documents based on business key (id)

## Next Steps

After CDC is working for both PostgreSQL and MongoDB, you can:
1. Set up consumers to process change events from both sources
2. Build real-time dashboards using the change streams
3. Set up data pipelines to sync between databases
4. Create real-time analytics dashboards

