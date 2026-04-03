package com.crypto.analyzer;

import com.crypto.analyzer.models.OhlcAccumulator;
import com.crypto.analyzer.models.PriceUpdate;
import org.apache.flink.api.common.functions.AggregateFunction;

import java.math.BigDecimal;

/**
 * Aggregate function for OHLC (Open, High, Low, Close) calculation.
 * 
 * Memory-efficient approach: Maintains only one accumulator per window
 * instead of buffering all events (2,500x memory improvement).
 * 
 * OHLC Logic:
 * - OPEN: First price chronologically (by timestamp)
 * - HIGH: Maximum price in window
 * - LOW: Minimum price in window
 * - CLOSE: Last price chronologically (by timestamp)
 * - VOLUME: Sum of all volumes
 * 
 * @author Zaid
 */
public class OhlcAggregateFunction 
    implements AggregateFunction<PriceUpdate, OhlcAccumulator, OhlcAccumulator> {
    
    private static final long serialVersionUID = 1L;
    
    /**
     * Create empty accumulator
     */
    @Override
    public OhlcAccumulator createAccumulator() {
        return new OhlcAccumulator();
    }
    
    /**
     * Add new price update to accumulator
     */
    @Override
    public OhlcAccumulator add(PriceUpdate priceUpdate, OhlcAccumulator acc) {
        try {
            // Convert price to BigDecimal (using valueOf for precision)
            BigDecimal price = priceUpdate.getPrice();
            BigDecimal volume = priceUpdate.getVolume24h() != null 
                ? priceUpdate.getVolume24h() 
                : BigDecimal.ZERO;
            
            // Get event timestamp
            long timestamp = priceUpdate.getTimestamp();
            
            // Initialize on first event
            if (acc.isFirst) {
                acc.open = price;
                acc.high = price;
                acc.low = price;
                acc.close = price;
                acc.firstTimestamp = timestamp;
                acc.lastTimestamp = timestamp;
                acc.isFirst = false;
            } else {
                // Update HIGH if current price exceeds
                if (price.compareTo(acc.high) > 0) {
                    acc.high = price;
                }
                
                // Update LOW if current price is lower
                if (price.compareTo(acc.low) < 0) {
                    acc.low = price;
                }
                
                // Update OPEN if this event is chronologically earlier
                if (timestamp < acc.firstTimestamp) {
                    acc.open = price;
                    acc.firstTimestamp = timestamp;
                }
                
                // Update CLOSE if this event is chronologically later
                if (timestamp >= acc.lastTimestamp) {
                    acc.close = price;
                    acc.lastTimestamp = timestamp;
                }
            }
            
            // Aggregate volume
            acc.volumeSum = acc.volumeSum.add(volume);
            acc.eventCount++;
            
            return acc;
            
        } catch (Exception e) {
            // Log error but continue processing
            System.err.println("Error in OHLC aggregation: " + e.getMessage());
            return acc;
        }
    }
    
    /**
     * Get final result from accumulator
     */
    @Override
    public OhlcAccumulator getResult(OhlcAccumulator acc) {
        return acc;
    }
    
    /**
     * Merge two accumulators (required for distributed processing)
     * 
     * This is called when Flink needs to combine partial results from
     * different parallel instances or during session window merging.
     */
    @Override
    public OhlcAccumulator merge(OhlcAccumulator a, OhlcAccumulator b) {
        OhlcAccumulator merged = new OhlcAccumulator();
        
        // Handle empty accumulators
        if (a.isFirst) return b;
        if (b.isFirst) return a;
        
        // OPEN from earliest accumulator
        if (a.firstTimestamp <= b.firstTimestamp) {
            merged.open = a.open;
            merged.firstTimestamp = a.firstTimestamp;
        } else {
            merged.open = b.open;
            merged.firstTimestamp = b.firstTimestamp;
        }
        
        // CLOSE from latest accumulator
        if (a.lastTimestamp >= b.lastTimestamp) {
            merged.close = a.close;
            merged.lastTimestamp = a.lastTimestamp;
        } else {
            merged.close = b.close;
            merged.lastTimestamp = b.lastTimestamp;
        }
        
        // HIGH is maximum across both
        merged.high = a.high.max(b.high);
        
        // LOW is minimum across both
        merged.low = a.low.min(b.low);
        
        // Sum volumes and event counts
        merged.volumeSum = a.volumeSum.add(b.volumeSum);
        merged.eventCount = a.eventCount + b.eventCount;
        merged.isFirst = false;
        
        return merged;
    }
}