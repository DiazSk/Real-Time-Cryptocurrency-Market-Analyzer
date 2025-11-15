package com.crypto.analyzer;

import com.crypto.analyzer.functions.OHLCAggregator;
import com.crypto.analyzer.functions.OHLCWindowFunction;
import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceUpdate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.SerializableTimestampAssigner;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.time.Duration;

/**
 * Main Flink job for cryptocurrency price aggregation with windowing.
 * 
 * Phase 3 - Week 5: Windowing and OHLC aggregation
 * - 60-second tumbling windows
 * - 10-second watermark delay for late data
 * - OHLC (Open-High-Low-Close) candle computation
 * - Robust error handling to prevent job crashes
 * 
 * @author Zaid
 */
public class CryptoPriceAggregator {
    
    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);
    
    // Configuration constants
    private static final String KAFKA_BOOTSTRAP_SERVERS = "kafka:29092";  // Docker internal
    private static final String KAFKA_TOPIC = "crypto-prices";
    private static final String KAFKA_GROUP_ID = "flink-crypto-analyzer";
    
    public static void main(String[] args) throws Exception {
        
        LOG.info("Starting Crypto Price Aggregator Flink Job...");
        
        // 1. Set up the Flink execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        // Set parallelism (matches TaskManager slots)
        env.setParallelism(1);
        
        // Enable checkpointing for fault tolerance (configured in flink-conf.yaml)
        // env.enableCheckpointing(60000); // 60 seconds - already configured globally
        
        LOG.info("Execution environment configured with parallelism: {}", env.getParallelism());
        
        // 2. Configure Kafka source
        KafkaSource<PriceUpdate> kafkaSource = KafkaSource.<PriceUpdate>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(KAFKA_TOPIC)
                .setGroupId(KAFKA_GROUP_ID)
                .setStartingOffsets(OffsetsInitializer.earliest())  // Read from beginning
                .setValueOnlyDeserializer(new PriceUpdateDeserializer())
                .build();
        
        LOG.info("Kafka source configured: bootstrap={}, topic={}, group={}", 
                KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, KAFKA_GROUP_ID);
        
        // 3. Configure watermark strategy for event time processing
        // - Extract timestamp from PriceUpdate events (with error handling!)
        // - Allow 10 seconds of out-of-orderness (watermark delay)
        // - Idle timeout prevents watermark stalls
        WatermarkStrategy<PriceUpdate> watermarkStrategy = WatermarkStrategy
                .<PriceUpdate>forBoundedOutOfOrderness(Duration.ofSeconds(10))
                .withTimestampAssigner(new SerializableTimestampAssigner<PriceUpdate>() {
                    @Override
                    public long extractTimestamp(PriceUpdate element, long recordTimestamp) {
                        try {
                            return element.getTimestampMillis();
                        } catch (Exception e) {
                            LOG.warn("Failed to extract timestamp, using record timestamp: {}", e.getMessage());
                            return recordTimestamp;  // Fallback to Kafka record timestamp
                        }
                    }
                })
                .withIdleness(Duration.ofMinutes(1));  // Critical: prevent idle partition stalls
        
        LOG.info("Watermark strategy configured: 10 second allowed lateness, 1 minute idle timeout");
        
        // 4. Create data stream with windowing and aggregation
        DataStream<PriceUpdate> priceStream = env
                .fromSource(kafkaSource, watermarkStrategy, "Kafka Source")
                .filter(priceUpdate -> priceUpdate != null && priceUpdate.isValid());  // Filter nulls and invalid messages
        
        LOG.info("Price stream created with event-time watermarks");
        
        // 5. Apply windowing and OHLC aggregation
        // - Key by symbol (BTC, ETH, etc.)
        // - 60-second tumbling windows
        // - Aggregate to OHLC candles with ProcessWindowFunction for window metadata
        DataStream<OHLCCandle> ohlcStream = priceStream
                .keyBy(PriceUpdate::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.seconds(60)))
                .aggregate(new OHLCAggregator(), new OHLCWindowFunction());
        
        LOG.info("OHLC aggregation configured: 60-second tumbling windows");
        
        // 6. Output results (print to console for now)
        ohlcStream.print();
        
        LOG.info("Data stream pipeline configured");
        
        // 7. Execute the job
        env.execute("Crypto Price Aggregator with OHLC Windowing");
        
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
