"use client";

import React, { useState } from "react";
import { usePortfolio } from "../contexts/PortfolioContext";
import { useSSE } from "../contexts/SSEContext";

function fmt(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function TradeBar() {
  const { executeTrade } = usePortfolio();
  const { prices } = useSSE();

  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const upperTicker = ticker.toUpperCase().trim();
  const qty = parseFloat(quantity);
  const currentPrice = upperTicker && prices[upperTicker] ? prices[upperTicker].price : null;
  const notional = currentPrice !== null && qty > 0 ? currentPrice * qty : null;
  const canTrade = upperTicker.length > 0 && currentPrice !== null && qty > 0 && !submitting;

  async function doTrade(side: "buy" | "sell") {
    if (!canTrade) return;
    setSubmitting(true);
    setFeedback(null);
    const result = await executeTrade(upperTicker, qty, side);
    setSubmitting(false);
    if (result.success) {
      setFeedback({ ok: true, msg: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${upperTicker}` });
      setQuantity("");
    } else {
      const code = result.error?.code ?? "error";
      const msgs: Record<string, string> = {
        insufficient_cash: "Insufficient cash",
        insufficient_shares: "Insufficient shares",
        unknown_ticker: "Unknown ticker",
        price_unavailable: "Price unavailable",
        bad_request: "Invalid request",
      };
      setFeedback({ ok: false, msg: msgs[code] ?? result.error?.message ?? "Trade failed" });
    }
  }

  return (
    <div
      style={{
        padding: "8px 14px",
        borderTop: "1px solid #30363d",
        backgroundColor: "#161b22",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
      }}
    >
      <div style={{ fontSize: 10, color: "#8b949e", letterSpacing: "0.1em", textTransform: "uppercase", marginRight: 4 }}>
        Trade
      </div>

      {/* Ticker */}
      <input
        value={ticker}
        onChange={(e) => {
          setTicker(e.target.value.toUpperCase());
          setFeedback(null);
        }}
        placeholder="TICKER"
        style={{
          background: "#1c2128",
          border: "1px solid #30363d",
          color: "#e6edf3",
          padding: "5px 8px",
          fontSize: 13,
          fontWeight: 700,
          width: 80,
          borderRadius: 3,
          outline: "none",
          fontFamily: "monospace",
        }}
      />

      {/* Quantity */}
      <input
        type="number"
        value={quantity}
        onChange={(e) => {
          setQuantity(e.target.value);
          setFeedback(null);
        }}
        placeholder="Qty"
        min="0.01"
        step="1"
        style={{
          background: "#1c2128",
          border: "1px solid #30363d",
          color: "#e6edf3",
          padding: "5px 8px",
          fontSize: 13,
          width: 70,
          borderRadius: 3,
          outline: "none",
          fontFamily: "monospace",
        }}
      />

      {/* Price preview */}
      {upperTicker && (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {currentPrice !== null ? (
            <span style={{ fontSize: 12, color: "#8b949e" }}>
              @ ${fmt(currentPrice)}
              {notional !== null && (
                <span style={{ color: "#484f58", marginLeft: 4 }}>= ${fmt(notional)}</span>
              )}
            </span>
          ) : (
            <span style={{ fontSize: 11, color: "#484f58" }}>
              {upperTicker.length > 0 ? "Not tracked" : ""}
            </span>
          )}
        </div>
      )}

      {/* Buy button */}
      <button
        disabled={!canTrade}
        onClick={() => doTrade("buy")}
        style={{
          background: canTrade ? "#753991" : "#30363d",
          border: "none",
          color: canTrade ? "#fff" : "#484f58",
          padding: "5px 14px",
          fontSize: 12,
          fontWeight: 700,
          borderRadius: 3,
          cursor: canTrade ? "pointer" : "not-allowed",
          letterSpacing: "0.05em",
          transition: "background 0.1s",
        }}
      >
        BUY
      </button>

      {/* Sell button */}
      <button
        disabled={!canTrade}
        onClick={() => doTrade("sell")}
        style={{
          background: canTrade ? "#f85149" : "#30363d",
          border: "none",
          color: canTrade ? "#fff" : "#484f58",
          padding: "5px 14px",
          fontSize: 12,
          fontWeight: 700,
          borderRadius: 3,
          cursor: canTrade ? "pointer" : "not-allowed",
          letterSpacing: "0.05em",
          transition: "background 0.1s",
        }}
      >
        SELL
      </button>

      {/* Feedback */}
      {feedback && (
        <span
          style={{
            fontSize: 11,
            color: feedback.ok ? "#3fb950" : "#f85149",
            marginLeft: 4,
          }}
        >
          {feedback.ok ? "✓" : "⚠"} {feedback.msg}
        </span>
      )}
    </div>
  );
}
