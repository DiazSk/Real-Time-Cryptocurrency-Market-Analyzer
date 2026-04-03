package com.crypto.analyzer;

import com.crypto.analyzer.models.OhlcAccumulator;
import com.crypto.analyzer.models.OhlcOutput;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

/**
 * Process Window Function to enrich OHLC aggregation with window metadata.
 * 
 * This function receives the aggregated OhlcAccumulator from OhlcAggregateFunction
 * and adds window-specific metadata (start time, end time) to create OhlcOutput.
 * 
 * The hybrid approach (AggregateFunction + ProcessWindowFunction) provides:
 * - Memory efficiency from AggregateFunction (only stores accumulator)
 * - Window metadata access from ProcessWindowFunction (window bounds)
 * 
 * @author Zaid
 */
public class OhlcWindowFunction 
    extends ProcessWindowFunction<OhlcAccumulator, OhlcOutput, String, TimeWindow> {
    
    private static final long serialVersionUID = 1L;
    
    /**
     * Process the window and add metadata to output
     * 
     * @param symbol Cryptocurrency symbol (BTC, ETH) - the key
     * @param context Window context with metadata
     * @param elements Iterable of OhlcAccumulator (only contains 1 element)
     * @param out Collector to emit results
     */
    @Override
    public void process(
            String symbol,
            Context context,
            Iterable<OhlcAccumulator> elements,
            Collector<OhlcOutput> out) {
        
        // Get the accumulator (only one element from AggregateFunction)
        OhlcAccumulator acc = elements.iterator().next();
        
        // Get window bounds
        TimeWindow window = context.window();
        long windowStart = window.getStart();
        long windowEnd = window.getEnd();
        
        // Get current processing time (for latency tracking)
        long processingTime = System.currentTimeMillis();
        
        // Create output with window metadata
        OhlcOutput output = new OhlcOutput(
            symbol,
            acc.open,
            acc.high,
            acc.low,
            acc.close,
            acc.volumeSum,
            windowStart,
            windowEnd,
            acc.eventCount,
            processingTime
        );
        
        // Emit the result
        out.collect(output);
    }
}