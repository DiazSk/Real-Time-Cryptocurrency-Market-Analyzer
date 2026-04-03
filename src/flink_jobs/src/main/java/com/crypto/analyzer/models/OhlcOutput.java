package com.crypto.analyzer.models;

import java.io.Serializable;
import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;

/**
 * Output POJO for OHLC (Open, High, Low, Close) aggregation results.
 * 
 * Contains OHLC candle data plus window metadata for downstream processing.
 * Uses BigDecimal for financial precision (avoids float/double rounding errors).
 * 
 * @author Zaid
 */
public class OhlcOutput implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    public String symbol;              // BTC, ETH
    
    public BigDecimal open;            // First price in window
    public BigDecimal high;            // Highest price in window
    public BigDecimal low;             // Lowest price in window
    public BigDecimal close;           // Last price in window
    public BigDecimal volume;          // Total volume in window
    
    public Long windowStart;           // Window start timestamp (milliseconds)
    public Long windowEnd;             // Window end timestamp (milliseconds)
    public Integer eventCount;         // Number of events in window
    public Timestamp processingTime;   // Processing timestamp (for latency tracking)
    
    /**
     * Default constructor (required for Flink POJO serialization)
     */
    public OhlcOutput() {}
    
    /**
     * Full constructor
     */
    public OhlcOutput(String symbol, BigDecimal open, BigDecimal high, 
                     BigDecimal low, BigDecimal close, BigDecimal volume,
                     Long windowStart, Long windowEnd, Integer eventCount,
                     Long processingTimestamp) {
        this.symbol = symbol;
        this.open = open;
        this.high = high;
        this.low = low;
        this.close = close;
        this.volume = volume;
        this.windowStart = windowStart;
        this.windowEnd = windowEnd;
        this.eventCount = eventCount;
        this.processingTime = new Timestamp(processingTimestamp);
    }
    
    /**
     * Get window start as readable timestamp
     */
    public String getWindowStartTime() {
        return Instant.ofEpochMilli(windowStart).toString();
    }
    
    /**
     * Get window end as readable timestamp
     */
    public String getWindowEndTime() {
        return Instant.ofEpochMilli(windowEnd).toString();
    }
    
    /**
     * Calculate price change percentage in window
     */
    public BigDecimal getPriceChangePercent() {
        if (open == null || open.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return close.subtract(open)
                   .divide(open, 4, BigDecimal.ROUND_HALF_EVEN)
                   .multiply(new BigDecimal("100"));
    }
    
    @Override
    public String toString() {
        return String.format(
            "[%s] %s OHLC | Open: %.2f | High: %.2f | Low: %.2f | Close: %.2f | Volume: %.2f | Events: %d",
            getWindowStartTime(),
            symbol,
            open,
            high,
            low,
            close,
            volume,
            eventCount
        );
    }
}
