package com.crypto.analyzer.models;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * OHLC (Open-High-Low-Close) candle for cryptocurrency price aggregation.
 * Represents aggregated price data over a time window.
 */
public class OHLCCandle implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    private String symbol;
    private Instant windowStart;
    private Instant windowEnd;
    private BigDecimal open;
    private BigDecimal high;
    private BigDecimal low;
    private BigDecimal close;
    private BigDecimal volumeSum;
    private int eventCount;
    
    // Default constructor
    public OHLCCandle() {
    }
    
    // Constructor with all fields
    public OHLCCandle(String symbol, Instant windowStart, Instant windowEnd,
                      BigDecimal open, BigDecimal high, BigDecimal low, BigDecimal close,
                      BigDecimal volumeSum, int eventCount) {
        this.symbol = symbol;
        this.windowStart = windowStart;
        this.windowEnd = windowEnd;
        this.open = open;
        this.high = high;
        this.low = low;
        this.close = close;
        this.volumeSum = volumeSum;
        this.eventCount = eventCount;
    }
    
    // Getters and Setters
    
    public String getSymbol() {
        return symbol;
    }
    
    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }
    
    public Instant getWindowStart() {
        return windowStart;
    }
    
    public void setWindowStart(Instant windowStart) {
        this.windowStart = windowStart;
    }
    
    public Instant getWindowEnd() {
        return windowEnd;
    }
    
    public void setWindowEnd(Instant windowEnd) {
        this.windowEnd = windowEnd;
    }
    
    public BigDecimal getOpen() {
        return open;
    }
    
    public void setOpen(BigDecimal open) {
        this.open = open;
    }
    
    public BigDecimal getHigh() {
        return high;
    }
    
    public void setHigh(BigDecimal high) {
        this.high = high;
    }
    
    public BigDecimal getLow() {
        return low;
    }
    
    public void setLow(BigDecimal low) {
        this.low = low;
    }
    
    public BigDecimal getClose() {
        return close;
    }
    
    public void setClose(BigDecimal close) {
        this.close = close;
    }
    
    public BigDecimal getVolumeSum() {
        return volumeSum;
    }
    
    public void setVolumeSum(BigDecimal volumeSum) {
        this.volumeSum = volumeSum;
    }
    
    public int getEventCount() {
        return eventCount;
    }
    
    public void setEventCount(int eventCount) {
        this.eventCount = eventCount;
    }
    
    @Override
    public String toString() {
        return String.format("[%s] %s OHLC | Open: %.2f | High: %.2f | Low: %.2f | Close: %.2f | Volume: %.2f | Events: %d",
                windowStart, symbol, open, high, low, close, 
                volumeSum != null ? volumeSum : BigDecimal.ZERO, eventCount);
    }
}

