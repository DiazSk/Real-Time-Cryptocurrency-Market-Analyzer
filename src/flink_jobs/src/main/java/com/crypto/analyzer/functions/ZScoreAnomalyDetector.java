package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.DetectorState;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.state.StateTtlConfig;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

/**
 * Flags a 1-minute candle whose log return is more than 4 standard deviations from the
 * symbol's exponentially weighted history (~60-candle span).
 *
 * <p>Rules: no alerts until 30 returns are seen, candles with fewer than 5 trades are not
 * scored, and only adjacent minutes are compared (after a quiet minute the detector
 * re-anchors instead of scoring a multi-minute move). The return is folded into the
 * history after scoring, so an outlier cannot mask itself. Thresholds stay constants
 * until sub-project 4 evaluates them.
 */
public class ZScoreAnomalyDetector extends KeyedProcessFunction<String, Candle, PriceAlert> {

    private static final long serialVersionUID = 1L;

    static final int WARMUP_RETURNS = 30;
    static final int MIN_TRADES = 5;
    static final double Z_THRESHOLD = 4.0;
    /** price_alerts.z_score is DECIMAL(10,4); an unclamped z from a near-flat history would overflow it. */
    static final double Z_CLAMP = 9999.0;
    private static final long ONE_MINUTE_MS = 60_000L;

    private transient ValueState<DetectorState> state;

    @Override
    public void open(Configuration parameters) {
        StateTtlConfig ttl = StateTtlConfig.newBuilder(Time.hours(1))
                .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
                .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
                .build();
        ValueStateDescriptor<DetectorState> descriptor =
                new ValueStateDescriptor<>("zscore-state", DetectorState.class);
        descriptor.enableTimeToLive(ttl);
        state = getRuntimeContext().getState(descriptor);
    }

    @Override
    public void processElement(Candle c, Context ctx, Collector<PriceAlert> out) throws Exception {
        DetectorState s = state.value();
        long start = c.windowStart.toEpochMilli();

        if (s == null) {
            s = new DetectorState();
        } else if (start - s.prevWindowStartMs == ONE_MINUTE_MS) {
            double r = Math.log(c.close.doubleValue() / s.prevClose.doubleValue());
            double z = s.zScore(r);
            if (s.returnsSeen >= WARMUP_RETURNS && c.tradeCount >= MIN_TRADES && Math.abs(z) > Z_THRESHOLD) {
                out.collect(PriceAlert.fromZScore(c, s.prevClose, Math.max(-Z_CLAMP, Math.min(Z_CLAMP, z))));
            }
            s.update(r);
        }
        // Non-adjacent candles (a quiet gap or a replayed window) only move the anchor.
        s.prevClose = c.close;
        s.prevWindowStartMs = start;
        state.update(s);
    }
}
