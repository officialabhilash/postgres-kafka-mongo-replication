# Real-Time Dashboards

A proof-of-concept for a real-time analytics dashboard built on a CDC (Change Data Capture) pipeline. Data mutations in PostgreSQL propagate automatically through Kafka to downstream consumers, enabling live Grafana dashboards with no polling.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Entry                                 │
│                    FastAPI  (port 8000)                             │
│                  POST / PATCH / DELETE /books                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ SQL writes
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                   PostgreSQL 17  (port 5432)                       │
│          wal_level=logical  │  cdc_publication  │  pgoutput slot   │
└────────────────────────────┬───────────────────────────────────────┘
                             │ WAL (logical replication)
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│            Kafka Connect / Debezium  (port 8083)                   │
│              postgres-source-connector (pgoutput)                  │
└────────────────────────────┬───────────────────────────────────────┘
                             │ CDC events (insert / update / delete)
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                  Apache Kafka  (port 9092, KRaft)                  │
│              topic: postgresql_server.public.books                 │
└─────────────────────────────────────────────────────────────────────┘
                             │ CDC events (insert / update / delete)
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Apache Flink  (local)                           │
│              aggregations / analytics transformations              │
└────────────────────────────┬───────────────────────────────────────┘
                             │ transformed time-series data
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                       TimescaleDB                                  │
│                     time-series tables                             │
└────────────────────────────┬───────────────────────────────────────┘
                             │ live SQL connection
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Grafana  (port 3000)                            │
│                    TimescaleDB datasource                          │
└────────────────────────────────────────────────────────────────────┘
```

## Components

| Service | Image | Port | Role |
|---|---|------|---|
| FastAPI | Python 3.14 | 8000 | REST API — data entry point |
| PostgreSQL | postgres:17 | 5432 | Source of truth, WAL CDC enabled |
| Kafka | apache/kafka (KRaft) | 9092 | Event streaming backbone |
| Kafka Connect | debezium/connect:3.0.0.Final | 8083 | CDC source connector |
| Kafka UI | provectuslabs/kafka-ui | 8080 | Kafka cluster browser |
| Apache Flink | flink (local) | 8081 | Stream processing, aggregations, analytics |
| TimescaleDB | timescale/timescaledb:latest-pg17 | 5431 | Time-series sink for analytics data |
| Grafana | grafana/grafana-oss | 3000 | Dashboard visualization |

## Data Flow

1. A client calls `POST /books`, `PATCH /books/{id}`, or `DELETE /books/{id}` on the FastAPI backend.
2. FastAPI writes the change to **PostgreSQL**.
3. PostgreSQL emits a WAL entry via the `cdc_publication` / `pgoutput` logical replication slot.
4. **Debezium** (Kafka Connect) reads the WAL and publishes a CDC envelope message to the Kafka topic `postgresql_server.public.books`.
5. **Apache Flink** consumes the topic, applies aggregations and analytics transformations, and writes the results to **TimescaleDB**.
6. **Grafana** queries TimescaleDB on a live connection and renders real-time dashboard panels.

## Project Structure

```
.
├── main.py                              # FastAPI app (REST + WebSocket)
├── initialize.sql                       # PostgreSQL schema, CDC user, publication, replication slot
├── docker-compose.local.yml             # All services
├── INITIALIZEME.sh                      # One-shot setup script
├── initialize_timescale.sql             # TimescaleDB schema, hypertables, analytics_user
├── postgres-connector-config.json       # Debezium PostgreSQL source connector config
├── register-postgres-connector.sh       # Register / update PostgreSQL connector via REST
├── delete-postgres-connector.sh         # Delete PostgreSQL connector
├── flink/                               # Flink jobs
├── data/                                # Persistent volumes (postgres, kafka, grafana)
└── requirements.txt                     # Python dependencies
```

## Prerequisites

- Docker and Docker Compose
- Python 3.14+ with `pip`
- Connector JARs in `./connectors/debezium` and `./connectors/mongodb` (excluded from repo)

## Quick Start

### 1. Start all services and register connectors

```bash
chmod +x INITIALIZEME.sh
./INITIALIZEME.sh
```

This brings up all Docker services, waits for them to be ready, fixes volume permissions, then registers the PostgreSQL CDC connector.

### 2. Start the FastAPI backend

```bash
pip install -r requirements.txt
python main.py
```

API docs available at `http://localhost:8000/docs`.

### 3. Open Grafana

Navigate to `http://localhost:3000`. Anonymous access is enabled with Admin role.

Add a TimescaleDB datasource and create panels against the analytics tables written by Flink.

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/books` | Create a book |
| `GET` | `/books` | List books (pagination: `skip`, `limit`) |
| `GET` | `/books/{id}` | Get a book by ID |
| `PATCH` | `/books/{id}` | Partial update (title and/or pages) |
| `DELETE` | `/books/{id}` | Delete a book |

## PostgreSQL CDC Setup

`initialize.sql` configures the source database on first start:

- Creates the `books` table
- Creates a `cdc_user` with `REPLICATION` role and `SELECT` on `books`
- Sets `REPLICA IDENTITY FULL` so deletes/updates emit full row data
- Creates `cdc_publication` scoped to the `books` table
- Creates the `books_cdc_slot` logical replication slot (`pgoutput`)

## Connector Management

```bash
# Register or update connector
./register-postgres-connector.sh

# Remove connector
./delete-postgres-connector.sh
```
### NOTE: Be sure to add entry for kafka `echo "127.0.0.1 kafka" | sudo tee -a /etc/hosts` before pushing any data for the job. this is something that needs to be done manually. 
Connector config is in `postgres-connector-config.json`. Kafka Connect REST API is available at `http://localhost:8083`.

## Kafka UI

Browse topics, consumer groups, and connector status at `http://localhost:8080`.

## License

MIT