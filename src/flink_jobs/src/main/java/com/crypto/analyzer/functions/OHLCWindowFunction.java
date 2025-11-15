package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.OHLCCandle;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.time.Instant;

/**
 * Process window function to attach window metadata to OHLC candles.
 * Adds window start and end timestamps to the aggregated result.
 */
public class OHLCWindowFunction extends ProcessWindowFunction<OHLCCandle, OHLCCandle, String, TimeWindow> {
    
    @Override
    public void process(String key,
                       Context context,
                       Iterable<OHLCCandle> elements,
                       Collector<OHLCCandle> out) {
        
        // Get the single OHLC candle from the aggregator
        OHLCCandle candle = elements.iterator().next();
        
        // Add window metadata
        TimeWindow window = context.window();
        candle.setWindowStart(Instant.ofEpochMilli(window.getStart()));
        candle.setWindowEnd(Instant.ofEpochMilli(window.getEnd()));
        
        // Emit the enriched candle
        out.collect(candle);
    }
}

