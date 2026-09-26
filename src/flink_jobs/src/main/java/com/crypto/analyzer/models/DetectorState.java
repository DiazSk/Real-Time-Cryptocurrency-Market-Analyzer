package com.crypto.analyzer.models;

import java.math.BigDecimal;

/**
 * Per-symbol state of the z-score detector: an exponentially weighted mean and variance
 * of 1-minute log returns, plus the previous candle it scores against.
 * Public fields keep it a Flink POJO so it checkpoints efficiently.
 */
public class DetectorState {

    /** EWMA smoothing for a ~60-candle span. */
    public static final double ALPHA = 2.0 / (60 + 1);

    public double mean;
    public double variance;
    public int returnsSeen;
    public long prevWindowStartMs;
    public BigDecimal prevClose;

    public DetectorState() {}

    /** z-score of r against the history so far, or NaN when there is no spread yet. */
    public double zScore(double r) {
        return variance > 0 ? (r - mean) / Math.sqrt(variance) : Double.NaN;
    }

    /** Fold r into the EWMA mean and variance (incremental form). */
    public void update(double r) {
        double diff = r - mean;
        double incr = ALPHA * diff;
        mean += incr;
        variance = (1 - ALPHA) * (variance + diff * incr);
        returnsSeen++;
    }
}
