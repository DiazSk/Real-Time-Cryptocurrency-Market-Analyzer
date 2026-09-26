package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.time.Instant;

/** Stamps the aggregated candle with its window bounds. */
public class CandleWindowFunction extends ProcessWindowFunction<Candle, Candle, String, TimeWindow> {

    private static final long serialVersionUID = 1L;

    @Override
    public void process(String key, Context ctx, Iterable<Candle> elements, Collector<Candle> out) {
        Candle c = elements.iterator().next();
        c.windowStart = Instant.ofEpochMilli(ctx.window().getStart());
        c.windowEnd = Instant.ofEpochMilli(ctx.window().getEnd());
        out.collect(c);
    }
}
