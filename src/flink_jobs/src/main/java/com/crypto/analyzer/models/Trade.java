package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * One Coinbase trade as published by src/producers/coinbase_trades_producer.py.
 *
 * <p>Public fields plus a no-arg constructor keep this a Flink POJO (efficient state serialization).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class Trade implements Serializable {

    private static final long serialVersionUID = 1L;

    @JsonProperty("trade_id")    public long tradeId;
    @JsonProperty("symbol")      public String symbol;
    @JsonProperty("price")       public BigDecimal price;
    @JsonProperty("size")        public BigDecimal size;
    @JsonProperty("side")        public String side;
    @JsonProperty("sequence")    public long sequence;
    @JsonProperty("event_time")  public Instant eventTime;
    @JsonProperty("ingest_time") public Instant ingestTime;

    public Trade() {}

    public Trade(long tradeId, String symbol, BigDecimal price, BigDecimal size, String side,
                 long sequence, Instant eventTime, Instant ingestTime) {
        this.tradeId = tradeId;
        this.symbol = symbol;
        this.price = price;
        this.size = size;
        this.side = side;
        this.sequence = sequence;
        this.eventTime = eventTime;
        this.ingestTime = ingestTime;
    }

    public String getSymbol() {
        return symbol;
    }

    public long getEventTimeMillis() {
        return eventTime.toEpochMilli();
    }

    public boolean isValid() {
        return tradeId > 0 && symbol != null && eventTime != null && ingestTime != null
                && price != null && price.signum() > 0
                && size != null && size.signum() > 0;
    }
}
