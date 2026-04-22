package com.crypto.analyzer;

import com.crypto.analyzer.functions.AnomalyDetector;
import com.crypto.analyzer.functions.OHLCAggregator;
import com.crypto.analyzer.functions.OHLCWindowFunction;
import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.OhlcDatabaseRecord;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.PriceUpdate;
import com.crypto.analyzer.sinks.RedisSinkFunction;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.SerializableTimestampAssigner;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.runtime.state.hashmap.HashMapStateBackend;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.environment.CheckpointConfig;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.jdbc.JdbcExecutionOptions;
import org.apache.flink.connector.jdbc.JdbcSink;
import org.apache.flink.connector.jdbc.JdbcStatementBuilder;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Duration;

/**
 * Main Flink streaming job: multi-window OHLC aggregation with PostgreSQL and Redis sinks.
 *
 * <p>Checkpointing is enabled with EXACTLY_ONCE mode so that the JDBC sink can participate
 * in two-phase commit and the job can recover from failure without data loss or duplication.
 * Parallelism is derived from FLINK_PARALLELISM env var (default 4) to match Kafka partitions.
 */
public class CryptoPriceAggregator {
    
    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);
    
    private static final String KAFKA_BOOTSTRAP_SERVERS = getEnvOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092");
    private static final String INPUT_TOPIC = getEnvOrDefault("KAFKA_INPUT_TOPIC", "crypto-prices");
    private static final String ALERT_TOPIC = getEnvOrDefault("KAFKA_ALERT_TOPIC", "crypto-alerts");
    private static final String CONSUMER_GROUP_ID = getEnvOrDefault("KAFKA_CONSUMER_GROUP", "flink-crypto-postgres-analyzer");

    private static final String POSTGRES_HOST = getEnvOrDefault("POSTGRES_HOST", "postgres");
    private static final String POSTGRES_PORT = getEnvOrDefault("POSTGRES_PORT", "5432");
    private static final String POSTGRES_DB = getEnvOrDefault("POSTGRES_DB", "crypto_db");
    private static final String POSTGRES_URL = String.format("jdbc:postgresql://%s:%s/%s", POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB);
    private static final String POSTGRES_USER = getEnvOrDefault("POSTGRES_USER", "crypto_user");
    private static final String POSTGRES_PASSWORD = getEnvOrDefault("POSTGRES_PASSWORD", "crypto_pass");

    private static final String REDIS_HOST = getEnvOrDefault("REDIS_HOST", "redis");
    private static final int REDIS_PORT = Integer.parseInt(getEnvOrDefault("REDIS_PORT", "6379"));

    // Default parallelism matches the number of Kafka partitions so each task slot
    // owns exactly one partition, eliminating unnecessary shuffles.
    private static final int PARALLELISM = Integer.parseInt(getEnvOrDefault("FLINK_PARALLELISM", "4"));
    
    /**
     * Get environment variable with fallback default value.
     * This allows configuration via environment variables without recompiling.
     */
    private static String getEnvOrDefault(String key, String defaultValue) {
        String value = System.getenv(key);
        if (value == null || value.trim().isEmpty()) {
            LOG.info("Using default for {}: {}", key, key.contains("PASSWORD") ? "****" : defaultValue);
            return defaultValue;
        }
        LOG.info("Using env for {}: {}", key, key.contains("PASSWORD") ? "****" : value);
        return value;
    }
    
    public static void main(String[] args) throws Exception {
        
        LOG.info("Starting Crypto Aggregator with PostgreSQL Sink...");

        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(PARALLELISM);

        // Chandy-Lamport distributed snapshots via Flink's asynchronous barrier snapshotting.
        // 60-second interval balances recovery time against checkpoint overhead on this topology.
        // RETAIN_ON_CANCELLATION keeps the latest checkpoint so the job restarts from a known
        // consistent state rather than replaying the full Kafka topic from the beginning.
        env.enableCheckpointing(60_000, CheckpointingMode.EXACTLY_ONCE);
        CheckpointConfig cpConfig = env.getCheckpointConfig();
        cpConfig.setCheckpointTimeout(120_000);
        cpConfig.setMinPauseBetweenCheckpoints(30_000);
        cpConfig.setMaxConcurrentCheckpoints(1);
        cpConfig.setExternalizedCheckpointCleanup(
                CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);
        cpConfig.setCheckpointStorage("file:///opt/flink/checkpoints");

        LOG.info("Execution environment configured with parallelism={}", PARALLELISM);
        
        // Configure Kafka source
        KafkaSource<PriceUpdate> kafkaSource = KafkaSource.<PriceUpdate>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(INPUT_TOPIC)
                .setGroupId(CONSUMER_GROUP_ID)
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new PriceUpdateDeserializer())
                .build();
        
        LOG.info("Kafka source configured");
        
        // Configure watermark strategy
        WatermarkStrategy<PriceUpdate> watermarkStrategy = WatermarkStrategy
                .<PriceUpdate>forBoundedOutOfOrderness(Duration.ofSeconds(10))
                .withTimestampAssigner(new SerializableTimestampAssigner<PriceUpdate>() {
                    @Override
                    public long extractTimestamp(PriceUpdate element, long recordTimestamp) {
                        try {
                            return element.getTimestampMillis();
                        } catch (Exception e) {
                            LOG.warn("Timestamp extraction failed, using record timestamp");
                            return recordTimestamp;
                        }
                    }
                })
                .withIdleness(Duration.ofMinutes(1));
        
        LOG.info("Watermark strategy configured");
        
        // Create base price stream
        DataStream<PriceUpdate> priceStream = env
                .fromSource(kafkaSource, watermarkStrategy, "Crypto Price Source")
                .filter(priceUpdate -> priceUpdate != null && priceUpdate.isValid())
                .name("Filter Invalid Prices");
        
        LOG.info("Base price stream created");
        
        // 1-Minute Windows with PostgreSQL + Redis sinks
        DataStream<OHLCCandle> ohlc1min = priceStream
                .keyBy(PriceUpdate::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(1)))
                .aggregate(new OHLCAggregator(), new OHLCWindowFunction())
                .name("1-Min OHLC");
        
        // Print to console
        ohlc1min
                .map(candle -> "📊 [1-MIN] " + candle.toString())
                .print()
                .name("Print 1-Min OHLC");
        
        // Convert to database records
        DataStream<OhlcDatabaseRecord> dbRecords = ohlc1min
                .map(OhlcDatabaseRecord::fromOhlcCandle)
                .filter(OhlcDatabaseRecord::isValid)
                .name("Map to DB Records");
        
        // Write to PostgreSQL with UPSERT
        dbRecords.addSink(createPostgresSink()).name("PostgreSQL Sink");
        
        // Write to Redis cache (latest candles) - use configurable Redis connection
        ohlc1min.addSink(new RedisSinkFunction(REDIS_HOST, REDIS_PORT, 300)).name("Redis Cache Sink");
        
        LOG.info("1-minute windows with PostgreSQL and Redis sinks configured");
        
        // 5-Minute Windows
        DataStream<OHLCCandle> ohlc5min = priceStream
                .keyBy(PriceUpdate::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(5)))
                .aggregate(new OHLCAggregator(), new OHLCWindowFunction())
                .name("5-Min OHLC");
        
        ohlc5min
                .map(candle -> "📊 [5-MIN] " + candle.toString())
                .print()
                .name("Print 5-Min OHLC");
        
        LOG.info("5-minute windows configured");
        
        // 15-Minute Windows
        DataStream<OHLCCandle> ohlc15min = priceStream
                .keyBy(PriceUpdate::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(15)))
                .aggregate(new OHLCAggregator(), new OHLCWindowFunction())
                .name("15-Min OHLC");
        
        ohlc15min
                .map(candle -> "📊 [15-MIN] " + candle.toString())
                .print()
                .name("Print 15-Min OHLC");
        
        LOG.info("15-minute windows configured");
        
        // Anomaly Detection
        DataStream<PriceAlert> alerts = ohlc1min
                .keyBy(OHLCCandle::getSymbol)
                .process(new AnomalyDetector())
                .name("Anomaly Detector");
        
        alerts.print().name("Print Alerts");
        
        // Write alerts to Kafka
        KafkaSink<PriceAlert> alertSink = KafkaSink.<PriceAlert>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(ALERT_TOPIC)
                        .setValueSerializationSchema(new PriceAlertSerializer())
                        .build())
                // EXACTLY_ONCE ties Kafka producer transactions to Flink checkpoints,
                // keeping the alert sink consistent with the job-level guarantee.
                .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
                .build();
        
        alerts.sinkTo(alertSink).name("Alert Kafka Sink");
        
        LOG.info("Anomaly detection with Kafka sink configured");
        
        env.execute("Crypto Aggregator with PostgreSQL Sink");
    }
    
    private static SinkFunction<OhlcDatabaseRecord> createPostgresSink() {
        String upsertSql =
            "INSERT INTO price_aggregates_1m " +
            "(crypto_id, window_start, window_end, open_price, high_price, low_price, " +
            " close_price, avg_price, volume_sum, trade_count) " +
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
            "ON CONFLICT (crypto_id, window_start) " +
            "DO UPDATE SET " +
            "  window_end = EXCLUDED.window_end, " +
            "  open_price = EXCLUDED.open_price, " +
            "  high_price = EXCLUDED.high_price, " +
            "  low_price = EXCLUDED.low_price, " +
            "  close_price = EXCLUDED.close_price, " +
            "  avg_price = EXCLUDED.avg_price, " +
            "  volume_sum = EXCLUDED.volume_sum, " +
            "  trade_count = EXCLUDED.trade_count, " +
            "  created_at = CURRENT_TIMESTAMP";
        
        JdbcStatementBuilder<OhlcDatabaseRecord> statementBuilder =
            new JdbcStatementBuilder<OhlcDatabaseRecord>() {
                @Override
                public void accept(PreparedStatement ps, OhlcDatabaseRecord record) throws SQLException {
                    ps.setInt(1, record.getCryptoId());
                    ps.setTimestamp(2, record.getWindowStart());
                    ps.setTimestamp(3, record.getWindowEnd());
                    ps.setBigDecimal(4, record.getOpenPrice());
                    ps.setBigDecimal(5, record.getHighPrice());
                    ps.setBigDecimal(6, record.getLowPrice());
                    ps.setBigDecimal(7, record.getClosePrice());
                    ps.setBigDecimal(8, record.getAvgPrice());
                    ps.setBigDecimal(9, record.getVolumeSum());
                    ps.setInt(10, record.getTradeCount());
                }
            };
        
        JdbcExecutionOptions executionOptions = JdbcExecutionOptions.builder()
                .withBatchSize(100)
                .withBatchIntervalMs(5000)
                .withMaxRetries(3)
                .build();

        JdbcConnectionOptions connectionOptions = new JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
                .withUrl(POSTGRES_URL)
                .withDriverName("org.postgresql.Driver")
                .withUsername(POSTGRES_USER)
                .withPassword(POSTGRES_PASSWORD)
                .build();
        
        return JdbcSink.sink(
            upsertSql,
            statementBuilder,
            executionOptions,
            connectionOptions
        );
    }
    
    /**
     * Deserializer for PriceUpdate from Kafka JSON
     */
    private static class PriceUpdateDeserializer extends AbstractDeserializationSchema<PriceUpdate> {
        
        private static final long serialVersionUID = 1L;
        private transient ObjectMapper objectMapper;
        
        @Override
        public void open(InitializationContext context) throws Exception {
            super.open(context);
            objectMapper = new ObjectMapper();
            objectMapper.registerModule(new JavaTimeModule());
        }
        
        @Override
        public PriceUpdate deserialize(byte[] message) throws IOException {
            if (objectMapper == null) {
                objectMapper = new ObjectMapper();
                objectMapper.registerModule(new JavaTimeModule());
            }
            
            try {
                return objectMapper.readValue(message, PriceUpdate.class);
            } catch (Exception e) {
                LOG.error("Deserialization error: {}", e.getMessage());
                return null;
            }
        }
    }
    
    /**
     * Serializer for PriceAlert to Kafka JSON
     */
    private static class PriceAlertSerializer implements SerializationSchema<PriceAlert> {
        
        private static final long serialVersionUID = 1L;
        
        private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper()
                .registerModule(new JavaTimeModule());
        
        @Override
        public byte[] serialize(PriceAlert alert) {
            try {
                if (alert == null) {
                    LOG.error("Attempting to serialize null PriceAlert!");
                    return "{}".getBytes(StandardCharsets.UTF_8);
                }
                
                if (alert.getSymbol() == null || alert.getAlertType() == null) {
                    LOG.error("PriceAlert has null critical fields: symbol={}, alertType={}", 
                            alert.getSymbol(), alert.getAlertType());
                }
                
                byte[] bytes = OBJECT_MAPPER.writeValueAsBytes(alert);
                LOG.debug("Serialized alert: {} bytes", bytes.length);
                return bytes;
                
            } catch (Exception e) {
                LOG.error("Alert serialization error for symbol {}: {}", 
                        alert != null ? alert.getSymbol() : "null", 
                        e.getMessage(), e);
                return "{\"error\":\"serialization_failed\"}".getBytes(StandardCharsets.UTF_8);
            }
        }
    }
}
