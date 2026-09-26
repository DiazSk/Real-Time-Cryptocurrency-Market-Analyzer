package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Counts trades that arrived after their 1-minute window closed (Flink metric: lateTrades). */
public class LateTradeCounter extends RichMapFunction<Trade, Trade> {

    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(LateTradeCounter.class);

    private transient Counter lateTrades;

    @Override
    public void open(Configuration parameters) {
        lateTrades = getRuntimeContext().getMetricGroup().counter("lateTrades");
    }

    @Override
    public Trade map(Trade t) {
        lateTrades.inc();
        LOG.debug("Late trade {} {} at {}", t.symbol, t.tradeId, t.eventTime);
        return t;
    }
}
