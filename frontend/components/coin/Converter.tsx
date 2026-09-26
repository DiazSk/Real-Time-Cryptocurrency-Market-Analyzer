"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowDownUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const amountFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

/** Converts an amount of the coin into any currency CoinGecko quotes it in. */
const Converter = ({ symbol, icon, priceList }: ConverterProps) => {
  const [currency, setCurrency] = useState("usd");
  const [amount, setAmount] = useState("10");
  const converted = (parseFloat(amount) || 0) * (priceList[currency] || 0);
  const sym = symbol.toUpperCase();

  return (
    <section aria-labelledby="converter-heading">
      <h2 id="converter-heading" className="heading mb-3">
        Convert {sym}
      </h2>

      <div className="surface overflow-hidden">
        <label className="flex items-center gap-3 px-4 py-3">
          <span className="sr-only">Amount of {sym}</span>
          <Input
            type="number"
            inputMode="decimal"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="num h-10 border-0 px-0 text-lg shadow-none focus-visible:ring-0"
          />
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <Image src={icon} alt="" width={18} height={18} className="rounded-full" />
            {sym}
          </span>
        </label>

        <div className="relative border-t">
          <span className="absolute top-0 left-1/2 flex size-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border bg-card text-muted-foreground">
            <ArrowDownUp size={13} strokeWidth={1.75} aria-hidden />
          </span>
        </div>

        <div className="flex items-center gap-3 bg-mist/60 px-4 py-3">
          <output className="num flex-1 text-lg text-foreground" aria-live="polite">
            {amountFmt.format(converted)}
          </output>
          <Select value={currency} onValueChange={setCurrency}>
            <SelectTrigger className="w-24 rounded-full" aria-label="Target currency">
              <SelectValue>{currency.toUpperCase()}</SelectValue>
            </SelectTrigger>
            <SelectContent className="max-h-72">
              {Object.keys(priceList).map((code) => (
                <SelectItem value={code} key={code}>
                  {code.toUpperCase()}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </section>
  );
};

export default Converter;
