package com.crypto.analyzer;

import com.crypto.analyzer.functions.OHLCAggregator;
import com.crypto.analyzer.functions.OHLCWindowFunction;
import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceUpdate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.util.OutputTag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;

/**
 * Main Flink job for cryptocurrency OHLC aggregation with event-time windowing.
 * 
 * Phase 3 - Week 5: Windowing and OHLC aggregation
 * 
 * Features:
 * - Event-time processing with bounded out-of-orderness watermarks
 * - 1-minute tumbling windows for OHLC calculation
 * - Allowed lateness and side outputs for late data
 * - Robust deserialization and timestamp handling
 * 
 * @author Zaid
 */
public class CryptoPriceAggregator {
    
    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);
    
    // Configuration constants
    private static final String KAFKA_BOOTSTRAP_SERVERS = "kafka:29092";  // Docker internal
    private static final String KAFKA_TOPIC = "crypto-prices";
    private static final String KAFKA_GROUP_ID = "flink-crypto-ohlc-analyzer";
    
    // Window configuration
    private static final int WINDOW_SIZE_MINUTES = 1;           // 1-minute OHLC candles
    private static final int OUT_OF_ORDERNESS_SECONDS = 10;    // Handle 10s network delays
    private static final int ALLOWED_LATENESS_SECONDS = 20;    // Keep window alive 20s for late events
    private static final int IDLE_TIMEOUT_MINUTES = 1;         // Prevent watermark stalls
    
    public static void main(String[] args) throws Exception {
        
        LOG.info("Starting Crypto OHLC Aggregator with Event-Time Windowing...");
        
        // 1. Set up the Flink execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        // Set parallelism (matches TaskManager slots)
        env.setParallelism(1);
        
        // Enable checkpointing for fault tolerance
        env.enableCheckpointing(60000);  // 60 seconds checkpoint interval
        
        LOG.info("Execution environment configured with parallelism: {}", env.getParallelism());
        
        // 2. Configure Kafka source
        KafkaSource<PriceUpdate> kafkaSource = KafkaSource.<PriceUpdate>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(KAFKA_TOPIC)
                .setGroupId(KAFKA_GROUP_ID)
                .setStartingOffsets(OffsetsInitializer.latest())  // Start from latest
                .setValueOnlyDeserializer(new PriceUpdateDeserializer())
                .build();
        
        LOG.info("Kafka source configured: bootstrap={}, topic={}, group={}", 
                KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, KAFKA_GROUP_ID);
        
        // 3. Configure watermark strategy for event time processing
        WatermarkStrategy<PriceUpdate> watermarkStrategy = WatermarkStrategy
                .<PriceUpdate>forBoundedOutOfOrderness(Duration.ofSeconds(OUT_OF_ORDERNESS_SECONDS))
                .withTimestampAssigner((priceUpdate, recordTimestamp) -> {
                    try {
                        return priceUpdate.getTimestampMillis();
                    } catch (Exception e) {
                        LOG.warn("Failed to extract timestamp, using record timestamp: {}", e.getMessage());
                        return recordTimestamp;  // Fallback to Kafka record timestamp
                    }
                })
                .withIdleness(Duration.ofMinutes(IDLE_TIMEOUT_MINUTES));

        // 3. Configure watermark strategy for event-time processing
        
        LOG.info("Watermark strategy configured: out-of-orderness={}s, idle-timeout={}min", 
                OUT_OF_ORDERNESS_SECONDS, IDLE_TIMEOUT_MINUTES);
        
        // 4. Create side output for late data monitoring
        final OutputTag<PriceUpdate> lateDataTag = new OutputTag<PriceUpdate>("late-crypto-prices"){};
        
        // 5. Create data stream from Kafka with watermarks
        DataStream<PriceUpdate> priceStream = env
                .fromSource(kafkaSource, watermarkStrategy, "Crypto Price Source")
                .filter(priceUpdate -> priceUpdate != null && priceUpdate.isValid());  // Filter out invalid messages
        
        LOG.info("Price stream created with validation filter");
        
        // 6. Apply windowing and OHLC aggregation
        SingleOutputStreamOperator<OHLCCandle> ohlcStream = priceStream
                .keyBy(PriceUpdate::getSymbol)  // Separate windows for BTC, ETH
                .window(TumblingEventTimeWindows.of(Time.minutes(WINDOW_SIZE_MINUTES)))
                .allowedLateness(Time.seconds(ALLOWED_LATENESS_SECONDS))  // Keep window alive for late events
                .sideOutputLateData(lateDataTag)  // Capture extremely late events
                .aggregate(
                    new OHLCAggregator(),  // Memory-efficient aggregation
                    new OHLCWindowFunction()      // Add window metadata
                );
        
        LOG.info("OHLC windowing configured: window={}min, lateness={}s", 
                WINDOW_SIZE_MINUTES, ALLOWED_LATENESS_SECONDS);
        
        // 7. Output results
        ohlcStream.print();
        
        // 8. Monitor late arrivals
        ohlcStream.getSideOutput(lateDataTag)
                .map(priceUpdate -> String.format(
                    "LATE DATA: %s at %s (%.2f)",
                    priceUpdate.getSymbol(),
                    Instant.ofEpochMilli(priceUpdate.getTimestampMillis()),
                    priceUpdate.getPrice()
                ))
                .print();
        
        LOG.info("Late data monitoring configured");
        
        // 9. Execute the job
        env.execute("Crypto OHLC Aggregator - 1-Minute Windows");
        
        LOG.info("Flink job execution completed");
    }
    
    /**
     * Custom deserializer for PriceUpdate objects from Kafka JSON messages
     * 
     * CRITICAL: Error handling prevents job crashes from malformed JSON
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
                // Log error but don't crash - return null to filter out later
                System.err.println("Failed to deserialize message: " + e.getMessage());
                return null;
            }
        }
    }
}