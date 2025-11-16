package com.crypto.analyzer.sinks;

import com.crypto.analyzer.models.OHLCCandle;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;
import redis.clients.jedis.exceptions.JedisException;

import java.time.Duration;

/**
 * Custom Redis sink for caching latest OHLC candles with Pub/Sub notification.
 * 
 * Phase 4 - Week 8 - Day 4-5: Enhanced with Redis Pub/Sub
 * 
 * Stores latest candle for each cryptocurrency with TTL of 5 minutes.
 * After writing to cache, publishes event to Redis Pub/Sub channel for real-time updates.
 * 
 * Key pattern: crypto:{SYMBOL}:latest
 * Value: JSON representation of OHLCCandle
 * TTL: 300 seconds (5 minutes)
 * Pub/Sub Channel: crypto:updates
 * 
 * Uses Jedis connection pool for thread-safety and efficiency.
 * 
 * @author Zaid
 */
public class RedisSinkFunction extends RichSinkFunction<OHLCCandle> {
    
    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(RedisSinkFunction.class);
    
    // Redis configuration
    private final String redisHost;
    private final int redisPort;
    private final int ttlSeconds;
    
    // Pub/Sub channel name
    private static final String PUBSUB_CHANNEL = "crypto:updates";
    
    // Connection pool
    private transient JedisPool jedisPool;
    private transient ObjectMapper objectMapper;
    
    /**
     * Constructor with default Redis connection (Docker internal)
     */
    public RedisSinkFunction() {
        this("redis", 6379, 300);  // 5 minutes TTL
    }
    
    /**
     * Constructor with custom configuration
     */
    public RedisSinkFunction(String redisHost, int redisPort, int ttlSeconds) {
        this.redisHost = redisHost;
        this.redisPort = redisPort;
        this.ttlSeconds = ttlSeconds;
    }
    
    /**
     * Initialize Redis connection pool and ObjectMapper
     */
    @Override
    public void open(Configuration parameters) throws Exception {
        super.open(parameters);
        
        LOG.info("Initializing Redis sink with Pub/Sub: {}:{}", redisHost, redisPort);
        
        // Configure Jedis connection pool
        JedisPoolConfig poolConfig = new JedisPoolConfig();
        poolConfig.setMaxTotal(10);                    // Max 10 connections
        poolConfig.setMaxIdle(5);                      // Keep 5 idle connections
        poolConfig.setMinIdle(1);                      // Minimum 1 idle connection
        poolConfig.setTestOnBorrow(true);              // Validate before use
        poolConfig.setTestOnReturn(true);              // Validate on return
        poolConfig.setTestWhileIdle(true);             // Test idle connections
        poolConfig.setMinEvictableIdleTime(Duration.ofSeconds(60));
        poolConfig.setTimeBetweenEvictionRuns(Duration.ofSeconds(30));
        poolConfig.setBlockWhenExhausted(true);        // Wait if pool exhausted
        poolConfig.setMaxWait(Duration.ofSeconds(5));  // Max wait time
        
        // Create connection pool
        jedisPool = new JedisPool(poolConfig, redisHost, redisPort, 2000);  // 2s timeout
        
        // Test connection
        try (Jedis jedis = jedisPool.getResource()) {
            String pong = jedis.ping();
            LOG.info("Redis connection successful: {}", pong);
        } catch (Exception e) {
            LOG.error("Failed to connect to Redis: {}", e.getMessage(), e);
            throw new RuntimeException("Redis connection failed", e);
        }
        
        // Initialize ObjectMapper for JSON serialization
        objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        
        LOG.info("Redis sink initialized successfully with Pub/Sub channel: {}", PUBSUB_CHANNEL);
    }
    
    /**
     * Write OHLC candle to Redis cache and publish event
     */
    @Override
    public void invoke(OHLCCandle candle, Context context) throws Exception {
        
        if (candle == null || candle.getSymbol() == null) {
            LOG.warn("Skipping null candle or candle with null symbol");
            return;
        }
        
        Jedis jedis = null;
        try {
            // Get connection from pool
            jedis = jedisPool.getResource();
            
            // Create Redis key: crypto:BTC:latest
            String key = String.format("crypto:%s:latest", candle.getSymbol());
            
            // Serialize candle to JSON
            String json = objectMapper.writeValueAsString(candle);
            
            // Write to Redis with TTL
            jedis.setex(key, ttlSeconds, json);
            
            // PUBLISH event to Pub/Sub channel for real-time updates
            // This notifies all subscribers that new data is available
            long subscriberCount = jedis.publish(PUBSUB_CHANNEL, json);
            
            LOG.debug("Cached and published {} candle to {} subscribers via {}", 
                     candle.getSymbol(), subscriberCount, PUBSUB_CHANNEL);
            
        } catch (JedisException e) {
            LOG.error("Redis error caching {}: {}", candle.getSymbol(), e.getMessage(), e);
            // Don't fail the job - Redis is cache, not critical storage
            
        } catch (Exception e) {
            LOG.error("Unexpected error caching {}: {}", candle.getSymbol(), e.getMessage(), e);
            
        } finally {
            // Return connection to pool
            if (jedis != null) {
                jedis.close();
            }
        }
    }
    
    /**
     * Close connection pool on shutdown
     */
    @Override
    public void close() throws Exception {
        super.close();
        
        if (jedisPool != null && !jedisPool.isClosed()) {
            LOG.info("Closing Redis connection pool...");
            jedisPool.close();
            LOG.info("Redis connection pool closed");
        }
    }
}
