package com.crypto.analyzer;

import com.crypto.analyzer.functions.AnomalyDetector;
import com.crypto.analyzer.functions.OHLCAggregator;
import com.crypto.analyzer.functions.OHLCWindowFunction;
import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.PriceUpdate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.SerializableTimestampAssigner;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Main Flink job for cryptocurrency multi-window aggregation and anomaly detection.
 * 
 * Phase 3 - Week 6: Multi-Window Processing + Anomaly Detection
 * 
 * Features:
 * - 1-minute, 5-minute, and 15-minute tumbling windows (parallel processing)
 * - OHLC calculation for all window sizes
 * - Anomaly detection on 1-minute windows (>5% price spike/drop)
 * - Alerts written to Kafka topic 'crypto-alerts'
 * - Event-time processing with watermarks
 * 
 * @author Zaid
 */
public class CryptoPriceAggregator {
    
    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);
    
    // Kafka configuration
    private static final String KAFKA_BOOTSTRAP_SERVERS = "kafka:29092";  // Docker internal
    private static final String INPUT_TOPIC = "crypto-prices";
    private static final String ALERT_TOPIC = "crypto-alerts";
    private static final String CONSUMER_GROUP_ID = "flink-crypto-multi-window-analyzer";
    
    public static void main(String[] args) throws Exception {
        
        LOG.info("Starting Multi-Window Crypto Price Aggregator with Anomaly Detection...");
        
        // 1. Set up Flink execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        
        LOG.info("Execution environment configured with parallelism: {}", env.getParallelism());
        
        // 2. Configure Kafka source
        KafkaSource<PriceUpdate> kafkaSource = KafkaSource.<PriceUpdate>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(INPUT_TOPIC)
                .setGroupId(CONSUMER_GROUP_ID)
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new PriceUpdateDeserializer())
                .build();
        
        LOG.info("Kafka source configured: servers={}, topic={}", KAFKA_BOOTSTRAP_SERVERS, INPUT_TOPIC);
        
        // 3. Configure watermark strategy (10s out-of-orderness, 1min idle timeout)
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
        
        LOG.info("Watermark strategy: 10s out-of-orderness, 1min idle timeout");
        
        // 4. Create base price stream
        DataStream<PriceUpdate> priceStream = env
                .fromSource(kafkaSource, watermarkStrategy, "Crypto Price Source")
                .filter(priceUpdate -> priceUpdate != null && priceUpdate.isValid())
                .name("Filter Invalid Prices");
        
        LOG.info("Base price stream created");
        
        // 5. Multi-Window Processing: Apply 1-min, 5-min, 15-min windows in parallel
        
        // 5a. 1-Minute Windows
        DataStream<OHLCCandle> ohlc1min = priceStream
                .keyBy(PriceUpdate::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(1)))
                .aggregate(new OHLCAggregator(), new OHLCWindowFunction())
                .name("1-Min OHLC");
        
        ohlc1min
                .map(candle -> "📊 [1-MIN] " + candle.toString())
                .print()
                .name("Print 1-Min OHLC");
        
        LOG.info("1-minute windows configured");
        
        // 5b. 5-Minute Windows
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
        
        // 5c. 15-Minute Windows
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
        
        // 6. Anomaly Detection: Check 1-minute windows for >5% price spikes
        // Uses KeyedProcessFunction with state to prevent duplicate alerts
        DataStream<PriceAlert> alerts = ohlc1min
                .keyBy(OHLCCandle::getSymbol)  // Key by symbol for state management
                .process(new AnomalyDetector())
                .name("Anomaly Detector");
        
        // Print alerts to console
        alerts.print().name("Print Alerts");
        
        LOG.info("Anomaly detection configured (>5% threshold)");
        
        // 7. Write alerts to Kafka topic 'crypto-alerts'
        KafkaSink<PriceAlert> alertSink = KafkaSink.<PriceAlert>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(ALERT_TOPIC)
                        .setValueSerializationSchema(new PriceAlertSerializer())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .build();
        
        alerts.sinkTo(alertSink).name("Alert Kafka Sink");
        
        LOG.info("Alert sink configured: topic={}", ALERT_TOPIC);
        
        // 8. Execute the job
        env.execute("Crypto Multi-Window Aggregator with Anomaly Detection");
        
        LOG.info("Job execution completed");
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
                return null;  // Will be filtered out
            }
        }
    }
    
    /**
     * Serializer for PriceAlert to Kafka JSON
     * Uses static ObjectMapper for thread-safe initialization
     * Enhanced with null-safety and detailed error logging
     */
    private static class PriceAlertSerializer implements SerializationSchema<PriceAlert> {
        
        private static final long serialVersionUID = 1L;
        
        // CRITICAL: Static ObjectMapper to avoid null issues
        private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper()
                .registerModule(new JavaTimeModule());
        
        @Override
        public byte[] serialize(PriceAlert alert) {
            try {
                // Null-safety check before serialization
                if (alert == null) {
                    LOG.error("Attempting to serialize null PriceAlert!");
                    return "{}".getBytes(StandardCharsets.UTF_8);
                }
                
                // Validate critical fields
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
                // Return minimal valid JSON on error to prevent sink crash
                return "{\"error\":\"serialization_failed\"}".getBytes(StandardCharsets.UTF_8);
            }
        }
    }
}
