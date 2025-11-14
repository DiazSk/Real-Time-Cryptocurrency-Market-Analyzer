package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * POJO representing a cryptocurrency price update from Kafka.
 * Maps to the JSON structure produced by the Python producer.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class PriceUpdate implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    @JsonProperty("symbol")
    private String symbol;
    
    @JsonProperty("price_usd")
    private BigDecimal price;
    
    @JsonProperty("volume_24h")
    private BigDecimal volume24h;
    
    @JsonProperty("market_cap")
    private BigDecimal marketCap;
    
    @JsonProperty("price_change_24h")
    private BigDecimal priceChange24h;
    
    @JsonProperty("timestamp")
    private String timestamp;  // ISO 8601 timestamp string from Python producer
    
    @JsonProperty("source")
    private String source;
    
    // Default constructor (required for Jackson deserialization)
    public PriceUpdate() {
    }
    
    // Constructor for testing
    public PriceUpdate(String symbol, BigDecimal price, String timestamp) {
        this.symbol = symbol;
        this.price = price;
        this.timestamp = timestamp;
    }
    
    // Getters and Setters
    
    public String getSymbol() {
        return symbol;
    }
    
    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }
    
    public BigDecimal getPrice() {
        return price;
    }
    
    public void setPrice(BigDecimal price) {
        this.price = price;
    }
    
    public BigDecimal getVolume24h() {
        return volume24h;
    }
    
    public void setVolume24h(BigDecimal volume24h) {
        this.volume24h = volume24h;
    }
    
    public BigDecimal getMarketCap() {
        return marketCap;
    }
    
    public void setMarketCap(BigDecimal marketCap) {
        this.marketCap = marketCap;
    }
    
    public BigDecimal getPriceChange24h() {
        return priceChange24h;
    }
    
    public void setPriceChange24h(BigDecimal priceChange24h) {
        this.priceChange24h = priceChange24h;
    }
    
    public String getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }
    
    public String getSource() {
        return source;
    }
    
    public void setSource(String source) {
        this.source = source;
    }
    
    // Helper methods
    
    /**
     * Get timestamp as Instant for event-time processing
     * Parses ISO 8601 timestamp string from Python producer
     */
    public Instant getInstant() {
        return Instant.parse(timestamp);
    }
    
    /**
     * Check if this price update is valid
     */
    public boolean isValid() {
        return symbol != null && !symbol.isEmpty() 
            && price != null && price.compareTo(BigDecimal.ZERO) > 0
            && timestamp != null && !timestamp.isEmpty();
    }
    
    @Override
    public String toString() {
        return "PriceUpdate{" +
                "symbol='" + symbol + '\'' +
                ", price=" + price +
                ", volume24h=" + volume24h +
                ", marketCap=" + marketCap +
                ", priceChange24h=" + priceChange24h +
                ", timestamp=" + timestamp +
                ", source='" + source + '\'' +
                '}';
    }
}
