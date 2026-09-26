package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

/**
 * Drops trades whose trade_id is not newer than the last one seen for the symbol.
 *
 * <p>Coinbase trade_ids are contiguous per product and the producer keeps per-partition order
 * (one in-flight request), so a Kafka retry duplicate always arrives right after its original.
 * One Long of keyed state is enough to remove it, and it is checkpointed with the source offsets,
 * so the guarantee survives restarts.
 */
public class DedupByTradeId extends KeyedProcessFunction<String, Trade, Trade> {

    private static final long serialVersionUID = 1L;

    private transient ValueState<Long> lastTradeId;
    private transient Counter duplicates;

    @Override
    public void open(Configuration parameters) {
        lastTradeId = getRuntimeContext().getState(new ValueStateDescriptor<>("last-trade-id", Types.LONG));
        duplicates = getRuntimeContext().getMetricGroup().counter("duplicateTrades");
    }

    @Override
    public void processElement(Trade trade, Context ctx, Collector<Trade> out) throws Exception {
        Long last = lastTradeId.value();
        if (last != null && trade.tradeId <= last) {
            duplicates.inc();
            return;
        }
        lastTradeId.update(trade.tradeId);
        out.collect(trade);
    }
}
