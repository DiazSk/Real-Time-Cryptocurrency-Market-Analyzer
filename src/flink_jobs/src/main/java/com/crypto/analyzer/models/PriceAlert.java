package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * Price alert POJO for anomaly detection.
 * 
 * Written to Kafka topic 'crypto-alerts' when price spike >5% detected.
 * 
 * @author Zaid
 */
public class PriceAlert implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    @JsonProperty("symbol")
    private String symbol;
    
    @JsonProperty("alert_type")
    private String alertType;  // "PRICE_SPIKE" or "PRICE_DROP"
    
    @JsonProperty("price_change_percent")
    private BigDecimal priceChangePercent;
    
    @JsonProperty("open_price")
    private BigDecimal openPrice;
    
    @JsonProperty("close_price")
    private BigDecimal closePrice;
    
    @JsonProperty("window_start")
    private String windowStart;
    
    @JsonProperty("window_end")
    private String windowEnd;
    
    @JsonProperty("timestamp")
    private String timestamp;
    
    @JsonProperty("severity")
    private String severity;  // "HIGH", "MEDIUM", "LOW"
    
    // Default constructor - Initialize with safe defaults to prevent NPE
    public PriceAlert() {
        this.severity = "LOW";  // Default severity
        this.priceChangePercent = BigDecimal.ZERO;
        this.openPrice = BigDecimal.ZERO;
        this.closePrice = BigDecimal.ZERO;
    }
    
    // Full constructor
    public PriceAlert(String symbol, String alertType, BigDecimal priceChangePercent,
                     BigDecimal openPrice, BigDecimal closePrice,
                     Instant windowStart, Instant windowEnd) {
        this.symbol = symbol;
        this.alertType = alertType;
        this.priceChangePercent = priceChangePercent;
        this.openPrice = openPrice;
        this.closePrice = closePrice;
        this.windowStart = windowStart.toString();
        this.windowEnd = windowEnd.toString();
        this.timestamp = Instant.now().toString();
        
        // Determine severity based on magnitude
        BigDecimal absChange = priceChangePercent.abs();
        if (absChange.compareTo(new BigDecimal("10")) >= 0) {
            this.severity = "HIGH";
        } else if (absChange.compareTo(new BigDecimal("7")) >= 0) {
            this.severity = "MEDIUM";
        } else {
            this.severity = "LOW";
        }
    }
    
    // Getters and Setters
    
    public String getSymbol() {
        return symbol;
    }
    
    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }
    
    public String getAlertType() {
        return alertType;
    }
    
    public void setAlertType(String alertType) {
        this.alertType = alertType;
    }
    
    public BigDecimal getPriceChangePercent() {
        return priceChangePercent;
    }
    
    public void setPriceChangePercent(BigDecimal priceChangePercent) {
        this.priceChangePercent = priceChangePercent;
    }
    
    public BigDecimal getOpenPrice() {
        return openPrice;
    }
    
    public void setOpenPrice(BigDecimal openPrice) {
        this.openPrice = openPrice;
    }
    
    public BigDecimal getClosePrice() {
        return closePrice;
    }
    
    public void setClosePrice(BigDecimal closePrice) {
        this.closePrice = closePrice;
    }
    
    public String getWindowStart() {
        return windowStart;
    }
    
    public void setWindowStart(String windowStart) {
        this.windowStart = windowStart;
    }
    
    public String getWindowEnd() {
        return windowEnd;
    }
    
    public void setWindowEnd(String windowEnd) {
        this.windowEnd = windowEnd;
    }
    
    public String getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }
    
    public String getSeverity() {
        return severity;
    }
    
    public void setSeverity(String severity) {
        this.severity = severity;
    }
    
    @Override
    public String toString() {
        // Null-safe toString to prevent NPE during serialization
        return String.format(
            "🚨 ALERT [%s] %s | Type: %s | Change: %.2f%% | Open: %.2f → Close: %.2f | Window: %s",
            severity != null ? severity : "UNKNOWN",
            symbol != null ? symbol : "UNKNOWN",
            alertType != null ? alertType : "UNKNOWN",
            priceChangePercent != null ? priceChangePercent : BigDecimal.ZERO,
            openPrice != null ? openPrice : BigDecimal.ZERO,
            closePrice != null ? closePrice : BigDecimal.ZERO,
            windowStart != null ? windowStart : "UNKNOWN"
        );
    }
}
