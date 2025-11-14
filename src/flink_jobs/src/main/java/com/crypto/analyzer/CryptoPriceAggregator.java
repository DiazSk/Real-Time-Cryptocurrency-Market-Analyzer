package com.crypto.analyzer;

import com.crypto.analyzer.models.PriceUpdate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

/**
 * Main Flink job for cryptocurrency price aggregation.
 * 
 * Phase 3 - Week 5: Basic setup to read from Kafka and print to console.
 * Future iterations will add windowing, aggregations, and database sinks.
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
        
        // 3. Create data stream from Kafka
        // Note: Watermark strategy will be added in Week 5 Day 4-7
        env.fromSource(kafkaSource, WatermarkStrategy.noWatermarks(), "Kafka Source")
                .filter(PriceUpdate::isValid)  // Filter out invalid messages
                .print();  // Print to console for now
        
        LOG.info("Data stream pipeline configured");
        
        // 4. Execute the job
        env.execute("Crypto Price Aggregator - Phase 3 Week 5");
        
        LOG.info("Flink job execution completed");
    }
    
    /**
     * Custom deserializer for PriceUpdate objects from Kafka JSON messages
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
            return objectMapper.readValue(message, PriceUpdate.class);
        }
    }
}
