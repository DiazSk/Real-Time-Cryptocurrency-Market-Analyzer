package com.crypto.analyzer;

import com.crypto.analyzer.functions.CandleAggregator;
import com.crypto.analyzer.functions.CandleWindowFunction;
import com.crypto.analyzer.functions.DedupByTradeId;
import com.crypto.analyzer.functions.LateTradeCounter;
import com.crypto.analyzer.functions.ZScoreAnomalyDetector;
import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.Trade;
import com.crypto.analyzer.sinks.JdbcSinks;
import com.crypto.analyzer.sinks.RedisSinkFunction;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.CheckpointConfig;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.DiscardingSink;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.util.OutputTag;
import org.apache.kafka.clients.consumer.OffsetResetStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Coinbase trades → dedup → raw trades + 1-minute OHLCV (+ Redis) → z-score alerts.
 *
 * <p>Delivery guarantees: the Kafka alert sink is exactly-once (transactions committed on
 * checkpoint). The JDBC sinks are at-least-once with idempotent SQL, so the result is
 * effectively-once. Redis is at-least-once with idempotent overwrites.
 */
public class CryptoPriceAggregator {

    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);

    private static final String KAFKA_BOOTSTRAP_SERVERS = getEnvOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092");
    private static final String INPUT_TOPIC = getEnvOrDefault("KAFKA_INPUT_TOPIC", "crypto-trades");
    private static final String ALERT_TOPIC = getEnvOrDefault("KAFKA_ALERT_TOPIC", "crypto-alerts");
    private static final String CONSUMER_GROUP_ID = getEnvOrDefault("KAFKA_CONSUMER_GROUP", "flink-crypto-trades");

    private static final String POSTGRES_URL = String.format("jdbc:postgresql://%s:%s/%s",
            getEnvOrDefault("POSTGRES_HOST", "postgres"),
            getEnvOrDefault("POSTGRES_PORT", "5432"),
            getEnvOrDefault("POSTGRES_DB", "crypto_db"));
    private static final String POSTGRES_USER = getEnvOrDefault("POSTGRES_USER", "crypto_user");
    private static final String POSTGRES_PASSWORD = getEnvOrDefault("POSTGRES_PASSWORD", "crypto_pass");

    private static final String REDIS_HOST = getEnvOrDefault("REDIS_HOST", "redis");
    private static final int REDIS_PORT = Integer.parseInt(getEnvOrDefault("REDIS_PORT", "6379"));

    // One subtask per crypto-trades partition (the topic is created with 4).
    private static final int PARALLELISM = Integer.parseInt(getEnvOrDefault("FLINK_PARALLELISM", "4"));

    private static final OutputTag<Trade> LATE_TRADES = new OutputTag<Trade>("late-trades") {};

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
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(PARALLELISM);

        // Checkpointing is defined here only, not in flink-conf.yaml. Kafka alert transactions
        // commit on each checkpoint, so 30 s is also the worst-case delay before a
        // read_committed consumer sees an alert. Storage comes from state.checkpoints.dir
        // (the shared flink_data volume, set in docker-compose.yml).
        env.enableCheckpointing(30_000, CheckpointingMode.EXACTLY_ONCE);
        CheckpointConfig cp = env.getCheckpointConfig();
        cp.setCheckpointTimeout(120_000);
        cp.setMinPauseBetweenCheckpoints(10_000);
        cp.setMaxConcurrentCheckpoints(1);
        cp.setExternalizedCheckpointCleanup(CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);

        KafkaSource<Trade> source = KafkaSource.<Trade>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(INPUT_TOPIC)
                .setGroupId(CONSUMER_GROUP_ID)
                // Resume from committed offsets when there is no checkpoint; earliest on first start.
                .setStartingOffsets(OffsetsInitializer.committedOffsets(OffsetResetStrategy.EARLIEST))
                .setValueOnlyDeserializer(new TradeDeserializer())
                .build();

        WatermarkStrategy<Trade> watermarks = WatermarkStrategy
                .<Trade>forBoundedOutOfOrderness(Duration.ofSeconds(2))
                .withTimestampAssigner((trade, recordTs) -> trade.getEventTimeMillis())
                // A partition with no trades for 30 s (quiet coins at night) must not stall windows.
                .withIdleness(Duration.ofSeconds(30));

        DataStream<Trade> trades = env
                .fromSource(source, watermarks, "Coinbase Trades")
                .uid("coinbase-trades-source")
                .keyBy(Trade::getSymbol)
                .process(new DedupByTradeId())
                .name("Dedup by trade_id")
                .uid("dedup-by-trade-id");

        JdbcConnectionOptions pg = new JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
                .withUrl(POSTGRES_URL)
                .withDriverName("org.postgresql.Driver")
                .withUsername(POSTGRES_USER)
                .withPassword(POSTGRES_PASSWORD)
                .build();

        trades.addSink(JdbcSinks.rawTrades(pg)).name("raw_trades Sink").uid("sink-raw-trades");

        SingleOutputStreamOperator<Candle> candles = trades
                .keyBy(Trade::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(1)))
                .sideOutputLateData(LATE_TRADES)
                .aggregate(new CandleAggregator(), new CandleWindowFunction())
                .name("1-Min OHLCV")
                .uid("ohlcv-1m-window");

        candles.getSideOutput(LATE_TRADES)
                .map(new LateTradeCounter()).name("Count Late Trades").uid("late-trade-counter")
                .addSink(new DiscardingSink<>()).name("Discard Late Trades").uid("discard-late-trades");

        candles.addSink(JdbcSinks.candles(pg)).name("price_aggregates_1m Sink").uid("sink-candles");
        candles.addSink(new RedisSinkFunction(REDIS_HOST, REDIS_PORT, 300)).name("Redis Latest + Pub/Sub").uid("sink-redis");

        DataStream<PriceAlert> alerts = candles
                .keyBy(Candle::getSymbol)
                .process(new ZScoreAnomalyDetector())
                .name("Z-Score Anomaly Detector")
                .uid("zscore-detector");

        alerts.addSink(JdbcSinks.alerts(pg)).name("price_alerts Sink").uid("sink-alerts");

        KafkaSink<PriceAlert> alertSink = KafkaSink.<PriceAlert>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(ALERT_TOPIC)
                        .setValueSerializationSchema(new PriceAlertSerializer())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
                // Required for EXACTLY_ONCE: unique transactional ids across restarts.
                .setTransactionalIdPrefix("crypto-alerts")
                // Flink's default producer transaction timeout (1 h) exceeds the broker's
                // transaction.max.timeout.ms (15 min) and fails the job; stay at the broker cap.
                .setProperty("transaction.timeout.ms", "900000")
                .build();

        alerts.sinkTo(alertSink).name("crypto-alerts Kafka Sink (exactly-once)").uid("sink-kafka-alerts");

        env.execute("Crypto trades -> OHLCV + z-score alerts");
    }

    /** Kafka JSON to Trade. Malformed, null, or invalid records return null, which the Kafka source skips. */
    static class TradeDeserializer extends AbstractDeserializationSchema<Trade> {

        private static final long serialVersionUID = 1L;
        private transient ObjectMapper mapper;

        @Override
        public void open(InitializationContext context) {
            mapper = new ObjectMapper().registerModule(new JavaTimeModule());
        }

        @Override
        public Trade deserialize(byte[] message) {
            // A Kafka tombstone (null record value) has no bytes to parse.
            if (message == null) {
                LOG.warn("Dropping null record");
                return null;
            }
            if (mapper == null) {
                // open() may not have run (e.g. unit tests calling deserialize directly).
                mapper = new ObjectMapper().registerModule(new JavaTimeModule());
            }
            try {
                Trade t = mapper.readValue(message, Trade.class);
                if (t == null) {
                    // The JSON literal `null` deserializes to a null Trade, not an exception.
                    LOG.warn("Dropping null trade: {}", new String(message, StandardCharsets.UTF_8));
                    return null;
                }
                if (t.isValid()) {
                    return t;
                }
                LOG.warn("Dropping invalid trade: {}", new String(message, StandardCharsets.UTF_8));
            } catch (IOException | RuntimeException e) {
                LOG.warn("Dropping undeserializable record: {}", e.getMessage());
            }
            return null;
        }
    }

    private static class PriceAlertSerializer implements SerializationSchema<PriceAlert> {

        private static final long serialVersionUID = 1L;
        private static final ObjectMapper MAPPER = new ObjectMapper();

        @Override
        public byte[] serialize(PriceAlert alert) {
            try {
                return MAPPER.writeValueAsBytes(alert);
            } catch (IOException e) {
                // Fail the job rather than write a placeholder into an exactly-once topic.
                throw new IllegalStateException("Cannot serialize alert for " + alert.symbol, e);
            }
        }
    }
}
