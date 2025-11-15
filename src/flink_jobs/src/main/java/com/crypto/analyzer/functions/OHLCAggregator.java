package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.OHLCCandle;
import com.crypto.analyzer.models.PriceUpdate;
import org.apache.flink.api.common.functions.AggregateFunction;

import java.math.BigDecimal;

/**
 * Aggregate function to compute OHLC candles from price updates.
 * Processes a window of price updates and produces a single OHLC candle.
 * 
 * Memory-efficient: Stores only accumulator state, not all events
 */
public class OHLCAggregator implements AggregateFunction<PriceUpdate, OHLCAggregator.Accumulator, OHLCCandle> {
    
    /**
     * Accumulator to hold intermediate aggregation state
     */
    public static class Accumulator {
        String symbol;
        BigDecimal open;
        BigDecimal high;
        BigDecimal low;
        BigDecimal close;
        BigDecimal volumeSum = BigDecimal.ZERO;
        int eventCount = 0;
        long firstTimestamp = Long.MAX_VALUE;
        long lastTimestamp = Long.MIN_VALUE;
    }
    
    @Override
    public Accumulator createAccumulator() {
        return new Accumulator();
    }
    
    @Override
    public Accumulator add(PriceUpdate value, Accumulator accumulator) {
        try {
            BigDecimal price = value.getPrice();
            BigDecimal volume = value.getVolume24h();
            
            // CRITICAL: Safe timestamp extraction with fallback
            long timestamp;
            try {
                timestamp = value.getTimestampMillis();
            } catch (Exception e) {
                System.err.println("Failed to extract timestamp, using current time: " + e.getMessage());
                timestamp = System.currentTimeMillis();
            }
            
            // Validate price before processing
            if (price == null || price.compareTo(BigDecimal.ZERO) <= 0) {
                System.err.println("Invalid price for " + value.getSymbol() + ": " + price);
                return accumulator;  // Skip this event
            }
            
            // Set symbol (first time only)
            if (accumulator.symbol == null) {
                accumulator.symbol = value.getSymbol();
            }
            
            // First price becomes the open price
            if (accumulator.eventCount == 0) {
                accumulator.open = price;
                accumulator.high = price;
                accumulator.low = price;
            } else {
                // Update high if current price is higher
                if (accumulator.high == null || price.compareTo(accumulator.high) > 0) {
                    accumulator.high = price;
                }
                
                // Update low if current price is lower
                if (accumulator.low == null || price.compareTo(accumulator.low) < 0) {
                    accumulator.low = price;
                }
            }
            
            // Last price always becomes the close price
            accumulator.close = price;
            
            // Sum up volumes
            if (volume != null) {
                accumulator.volumeSum = accumulator.volumeSum.add(volume);
            }
            
            // Track timestamps for ordering
            if (timestamp < accumulator.firstTimestamp) {
                accumulator.firstTimestamp = timestamp;
            }
            if (timestamp > accumulator.lastTimestamp) {
                accumulator.lastTimestamp = timestamp;
            }
            
            accumulator.eventCount++;
            
        } catch (Exception e) {
            // Log error but don't crash the job
            System.err.println("Error in OHLCAggregator.add(): " + e.getMessage());
            e.printStackTrace();
        }
        
        return accumulator;
    }
    
    @Override
    public OHLCCandle getResult(Accumulator accumulator) {
        OHLCCandle candle = new OHLCCandle();
        candle.setSymbol(accumulator.symbol != null ? accumulator.symbol : "UNKNOWN");
        candle.setOpen(accumulator.open);
        candle.setHigh(accumulator.high);
        candle.setLow(accumulator.low);
        candle.setClose(accumulator.close);
        candle.setVolumeSum(accumulator.volumeSum);
        candle.setEventCount(accumulator.eventCount);
        return candle;
    }
    
    @Override
    public Accumulator merge(Accumulator a, Accumulator b) {
        // Merge two accumulators (for session windows or when parallelizing)
        Accumulator merged = new Accumulator();
        
        try {
            merged.symbol = a.symbol != null ? a.symbol : b.symbol;
            
            // Open is from the earlier accumulator
            if (a.firstTimestamp < b.firstTimestamp) {
                merged.open = a.open;
                merged.firstTimestamp = a.firstTimestamp;
            } else {
                merged.open = b.open;
                merged.firstTimestamp = b.firstTimestamp;
            }
            
            // Close is from the later accumulator
            if (a.lastTimestamp > b.lastTimestamp) {
                merged.close = a.close;
                merged.lastTimestamp = a.lastTimestamp;
            } else {
                merged.close = b.close;
                merged.lastTimestamp = b.lastTimestamp;
            }
            
            // High is the maximum of both highs
            if (a.high != null && b.high != null) {
                merged.high = a.high.compareTo(b.high) > 0 ? a.high : b.high;
            } else {
                merged.high = a.high != null ? a.high : b.high;
            }
            
            // Low is the minimum of both lows
            if (a.low != null && b.low != null) {
                merged.low = a.low.compareTo(b.low) < 0 ? a.low : b.low;
            } else {
                merged.low = a.low != null ? a.low : b.low;
            }
            
            // Sum volumes and event counts
            merged.volumeSum = a.volumeSum.add(b.volumeSum);
            merged.eventCount = a.eventCount + b.eventCount;
            
        } catch (Exception e) {
            System.err.println("Error in OHLCAggregator.merge(): " + e.getMessage());
            e.printStackTrace();
        }
        
        return merged;
    }
}
