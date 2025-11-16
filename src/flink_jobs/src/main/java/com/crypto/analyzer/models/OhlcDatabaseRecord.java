package com.crypto.analyzer.models;

import com.crypto.analyzer.utils.CryptoIdMapper;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.Timestamp;
import java.time.Instant;

/**
 * Database record POJO for price_aggregates_1m table.
 * 
 * Maps OHLCCandle to PostgreSQL schema structure.
 * 
 * Table: price_aggregates_1m
 * Columns: id (auto), crypto_id, window_start, window_end, open_price, high_price,
 *          low_price, close_price, avg_price, volume_sum, trade_count, created_at
 * 
 * @author Zaid
 */
public class OhlcDatabaseRecord implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    // Database columns (id and created_at are auto-generated)
    private Integer cryptoId;
    private Timestamp windowStart;
    private Timestamp windowEnd;
    private BigDecimal openPrice;
    private BigDecimal highPrice;
    private BigDecimal lowPrice;
    private BigDecimal closePrice;
    private BigDecimal avgPrice;
    private BigDecimal volumeSum;
    private Integer tradeCount;
    
    /**
     * Default constructor (required for JDBC)
     */
    public OhlcDatabaseRecord() {}
    
    /**
     * Create from OHLCCandle
     */
    public static OhlcDatabaseRecord fromOhlcCandle(OHLCCandle candle) {
        OhlcDatabaseRecord record = new OhlcDatabaseRecord();
        
        // Map symbol to crypto_id (BTC→1, ETH→2)
        record.cryptoId = CryptoIdMapper.getCryptoId(candle.getSymbol());
        
        // Convert Instant to Timestamp for PostgreSQL
        record.windowStart = candle.getWindowStart() != null 
            ? Timestamp.from(candle.getWindowStart())
            : null;
        record.windowEnd = candle.getWindowEnd() != null
            ? Timestamp.from(candle.getWindowEnd())
            : null;
        
        // OHLC prices
        record.openPrice = candle.getOpen();
        record.highPrice = candle.getHigh();
        record.lowPrice = candle.getLow();
        record.closePrice = candle.getClose();
        
        // Calculate average price: (open + high + low + close) / 4
        if (candle.getOpen() != null && candle.getHigh() != null 
            && candle.getLow() != null && candle.getClose() != null) {
            record.avgPrice = candle.getOpen()
                    .add(candle.getHigh())
                    .add(candle.getLow())
                    .add(candle.getClose())
                    .divide(new BigDecimal("4"), 8, RoundingMode.HALF_EVEN);
        } else {
            record.avgPrice = BigDecimal.ZERO;
        }
        
        // Volume and trade count
        record.volumeSum = candle.getVolumeSum();
        record.tradeCount = candle.getEventCount();
        
        return record;
    }
    
    // Getters and Setters
    
    public Integer getCryptoId() {
        return cryptoId;
    }
    
    public void setCryptoId(Integer cryptoId) {
        this.cryptoId = cryptoId;
    }
    
    public Timestamp getWindowStart() {
        return windowStart;
    }
    
    public void setWindowStart(Timestamp windowStart) {
        this.windowStart = windowStart;
    }
    
    public Timestamp getWindowEnd() {
        return windowEnd;
    }
    
    public void setWindowEnd(Timestamp windowEnd) {
        this.windowEnd = windowEnd;
    }
    
    public BigDecimal getOpenPrice() {
        return openPrice;
    }
    
    public void setOpenPrice(BigDecimal openPrice) {
        this.openPrice = openPrice;
    }
    
    public BigDecimal getHighPrice() {
        return highPrice;
    }
    
    public void setHighPrice(BigDecimal highPrice) {
        this.highPrice = highPrice;
    }
    
    public BigDecimal getLowPrice() {
        return lowPrice;
    }
    
    public void setLowPrice(BigDecimal lowPrice) {
        this.lowPrice = lowPrice;
    }
    
    public BigDecimal getClosePrice() {
        return closePrice;
    }
    
    public void setClosePrice(BigDecimal closePrice) {
        this.closePrice = closePrice;
    }
    
    public BigDecimal getAvgPrice() {
        return avgPrice;
    }
    
    public void setAvgPrice(BigDecimal avgPrice) {
        this.avgPrice = avgPrice;
    }
    
    public BigDecimal getVolumeSum() {
        return volumeSum;
    }
    
    public void setVolumeSum(BigDecimal volumeSum) {
        this.volumeSum = volumeSum;
    }
    
    public Integer getTradeCount() {
        return tradeCount;
    }
    
    public void setTradeCount(Integer tradeCount) {
        this.tradeCount = tradeCount;
    }
    
    /**
     * Validate record has required fields
     */
    public boolean isValid() {
        return cryptoId != null && cryptoId > 0
            && windowStart != null
            && windowEnd != null
            && openPrice != null
            && highPrice != null
            && lowPrice != null
            && closePrice != null;
    }
    
    @Override
    public String toString() {
        return String.format(
            "DB Record[crypto_id=%d, window=%s, OHLC=(%.2f/%.2f/%.2f/%.2f), avg=%.2f, vol=%.2f, trades=%d]",
            cryptoId,
            windowStart,
            openPrice,
            highPrice,
            lowPrice,
            closePrice,
            avgPrice,
            volumeSum != null ? volumeSum : BigDecimal.ZERO,
            tradeCount
        );
    }
}
