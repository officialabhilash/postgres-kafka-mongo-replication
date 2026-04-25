import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.OpenContext;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.legacy.RichSinkFunction;
import org.apache.flink.streaming.api.functions.sink.legacy.SinkFunction;

import java.io.Serializable;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Timestamp;

public class FirstAggregationPipeline {

    // ── Config ─────────────────────────────────────────────────────────────
    // Kafka advertises "kafka:9092" inside Docker. If running Flink locally,
    // add '127.0.0.1 kafka' to /etc/hosts so the advertised address resolves.
    static final String KAFKA_BROKERS = "localhost:9092";
    static final String KAFKA_TOPIC = "postgresql_server.public.books";
    static final String KAFKA_GROUP = "flink-book-events-group";

    // Host port 5431 maps to timescale_db container port 5432 (docker-compose.local.yml)
    static final String TIMESCALE_URL = "jdbc:postgresql://localhost:5431/analytics";
    static final String TIMESCALE_USER = "admin";
    static final String TIMESCALE_PASS = "root";

    // ── BookEvent POJO ─────────────────────────────────────────────────────
    public static class BookEvent implements Serializable {
        public Timestamp eventTime;  // Debezium ts_ms — wall-clock time of the source DB commit
        public int bookId;
        public String title;
        public String author;
        public int pages;
        public int price;
        public String operation;  // INSERT | UPDATE | DELETE
    }

    // ── CDC parser ─────────────────────────────────────────────────────────
    // Debezium envelope with schemas.enable=false:
    //   { "before": {...|null}, "after": {...|null}, "op": "c|u|d|r", "ts_ms": <epoch_ms> }
    //
    //   op "c" (create)        → INSERT  — full row in "after",  "before" is null
    //   op "r" (snapshot read) → INSERT  — full row in "after",  "before" is null
    //   op "u" (update)        → UPDATE  — new state in "after", old state in "before"
    //   op "d" (delete)        → DELETE  — last known state in "before", "after" is null
    public static class DebeziumToBookEvent extends RichMapFunction<String, BookEvent> {

        private transient ObjectMapper mapper;

        @Override
        public void open(OpenContext ctx) {
            mapper = new ObjectMapper();
        }

        @Override
        public BookEvent map(String json) throws Exception {
            JsonNode root = mapper.readTree(json);
            String op = root.path("op").asText();

            // For deletes the final row state is preserved in "before"
            JsonNode row = op.equals("d") ? root.path("before") : root.path("after");

            BookEvent e = new BookEvent();
            e.bookId = row.get("id").asInt();
            e.title = row.get("title").asText();
            e.author = row.get("author").asText();
            e.pages = row.get("pages").asInt();
            e.price = row.get("price").asInt();
            e.operation = op.equals("u") ? "UPDATE"
                    : op.equals("d") ? "DELETE"
                    : "INSERT";   // "c" and "r" both represent a new row appearance
            e.eventTime = new Timestamp(root.path("ts_ms").asLong(System.currentTimeMillis()));
            return e;
        }
    }

    // ── JDBC sink ──────────────────────────────────────────────────────────
    // flink-connector-jdbc has no Flink 2.x release (StatefulSink was renamed
    // to SupportsWriterState in Flink 2.0 breaking binary compatibility).
    // Using legacy.RichSinkFunction with JDBC directly — addSink() still
    // accepts it in Flink 2.x via the legacy SinkFunction path.
    public static class TimescaleBookEventSink extends RichSinkFunction<BookEvent> {

        private static final String INSERT_SQL =
                "INSERT INTO book_events (event_time, book_id, title, author, pages, price, operation) " +
                        "VALUES (?, ?, ?, ?, ?, ?, ?)";

        private transient Connection conn;
        private transient PreparedStatement pstmt;

        @Override
        public void open(OpenContext ctx) throws Exception {
            // Flink's user classloader is isolated from the system DriverManager.
            // Explicitly loading the driver class registers it from the correct classloader.
            Class.forName("org.postgresql.Driver");
            conn = DriverManager.getConnection(TIMESCALE_URL, TIMESCALE_USER, TIMESCALE_PASS);
            pstmt = conn.prepareStatement(INSERT_SQL);
        }

        @Override
        public void invoke(BookEvent e, SinkFunction.Context ctx) throws Exception {
            pstmt.setTimestamp(1, e.eventTime);
            pstmt.setInt(2, e.bookId);
            pstmt.setString(3, e.title);
            pstmt.setString(4, e.author);
            pstmt.setInt(5, e.pages);
            pstmt.setInt(6, e.price);
            pstmt.setString(7, e.operation);
            pstmt.executeUpdate();
        }

        @Override
        public void close() throws Exception {
            if (pstmt != null) pstmt.close();
            if (conn  != null) conn.close();
        }
    }

    // ── Pipeline ───────────────────────────────────────────────────────────
    public static void main(String[] args) throws Exception {

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(30_000); // checkpoint every 30 s for at-least-once delivery

        // ── Source: Kafka CDC topic ──────────────────────────────────
        KafkaSource<String> kafkaSource = KafkaSource.<String>builder()
                .setBootstrapServers(KAFKA_BROKERS)
                .setTopics(KAFKA_TOPIC)
                .setGroupId(KAFKA_GROUP)
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        DataStream<String> rawCdc = env.fromSource(
                kafkaSource,
                WatermarkStrategy.noWatermarks(),
                "Kafka CDC — postgresql_server.public.books"
        );

        // ── Transform: parse Debezium envelope → BookEvent ──────────
        // Tombstone messages (null-value records on compacted topics) arrive as
        // blank strings via SimpleStringSchema — filter them before parsing.
        DataStream<BookEvent> bookEvents = rawCdc
                .filter(msg -> msg != null && !msg.isBlank())
                .map(new DebeziumToBookEvent())
                .name("Parse Debezium CDC → BookEvent");

        // ── Sink: book_events hypertable ─────────────────────────────
        // All three operation types are appended as distinct rows so Grafana
        // can plot the full change history of each book over time.
        bookEvents
                .addSink(new TimescaleBookEventSink())
                .name("Sink → TimescaleDB book_events");

        env.execute("Flink CDC → book_events");
    }
}
