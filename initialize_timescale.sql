-- TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─────────────────────────────────────────────────────────────
-- Table 1: book_events
-- One row per CDC event emitted by Flink for a book record.
-- Captures the full state of the row at event time so Grafana
-- can plot individual book metrics (price, pages) over time.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS book_events (
    event_time  TIMESTAMPTZ   NOT NULL,
    book_id     INT           NOT NULL,
    title       VARCHAR(255)  NOT NULL,
    author      VARCHAR(255)  NOT NULL,
    pages       INT           NOT NULL,
    price       INT           NOT NULL,
    operation   VARCHAR(10)   NOT NULL  -- INSERT | UPDATE | DELETE
);

SELECT create_hypertable('book_events', by_range('event_time'));

CREATE INDEX ON book_events (book_id, event_time DESC);
CREATE INDEX ON book_events (author,  event_time DESC);


-- ─────────────────────────────────────────────────────────────
-- Table 2: author_stats
-- One row per (author, time-bucket) written by Flink.
-- Summarises the catalogue state for each author inside a
-- tumbling window so Grafana can plot per-author trends.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS author_stats (
    bucket_time   TIMESTAMPTZ    NOT NULL,
    author        VARCHAR(255)   NOT NULL,
    total_books   INT            NOT NULL,
    avg_pages     NUMERIC(10, 2) NOT NULL,
    avg_price     NUMERIC(10, 2) NOT NULL,
    total_revenue INT            NOT NULL,  -- sum of price across all books
    min_price     INT            NOT NULL,
    max_price     INT            NOT NULL
);

SELECT create_hypertable('author_stats', by_range('bucket_time'));

CREATE INDEX ON author_stats (author, bucket_time DESC);


-- ─────────────────────────────────────────────────────────────
-- Read-only user for Grafana / external consumers
-- ─────────────────────────────────────────────────────────────
CREATE USER analytics_user WITH ENCRYPTED PASSWORD 'analytics';

GRANT CONNECT ON DATABASE analytics TO analytics_user;
GRANT USAGE   ON SCHEMA public       TO analytics_user;
GRANT SELECT  ON book_events         TO analytics_user;
GRANT SELECT  ON author_stats        TO analytics_user;