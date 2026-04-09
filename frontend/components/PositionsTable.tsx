"use client";

import React from "react";
import { usePortfolio } from "../contexts/PortfolioContext";
import { useSSE } from "../contexts/SSEContext";

function fmt(n: number, decimals = 2) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function PositionsTable() {
  const { portfolio } = usePortfolio();
  const { prices } = useSSE();

  const positions = portfolio?.positions ?? [];

  const rows = positions.map((p) => {
    const currentPrice = prices[p.ticker]?.price ?? p.current_price;
    const unrealizedPnl = (currentPrice - p.avg_cost) * p.quantity;
    const pnlPct = p.avg_cost > 0 ? ((currentPrice - p.avg_cost) / p.avg_cost) * 100 : 0;
    return { ...p, currentPrice, unrealizedPnl, pnlPct };
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          padding: "6px 14px",
          borderBottom: "1px solid #30363d",
          fontSize: 10,
          color: "#8b949e",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          flexShrink: 0,
        }}
      >
        Positions
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {rows.length === 0 ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "#484f58",
              fontSize: 12,
            }}
          >
            No open positions
          </div>
        ) : (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #30363d" }}>
                {["Ticker", "Qty", "Avg Cost", "Price", "P&L", "P&L %"].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: "5px 10px",
                      textAlign: h === "Ticker" ? "left" : "right",
                      color: "#484f58",
                      fontWeight: 500,
                      fontSize: 10,
                      letterSpacing: "0.05em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const pnlColor = row.unrealizedPnl >= 0 ? "#3fb950" : "#f85149";
                return (
                  <tr
                    key={row.ticker}
                    style={{ borderBottom: "1px solid #1c2128" }}
                  >
                    <td style={{ padding: "6px 10px", color: "#e6edf3", fontWeight: 700 }}>
                      {row.ticker}
                    </td>
                    <td style={{ padding: "6px 10px", textAlign: "right", color: "#8b949e" }}>
                      {fmt(row.quantity, row.quantity % 1 === 0 ? 0 : 4)}
                    </td>
                    <td style={{ padding: "6px 10px", textAlign: "right", color: "#8b949e" }}>
                      ${fmt(row.avg_cost)}
                    </td>
                    <td style={{ padding: "6px 10px", textAlign: "right", color: "#e6edf3" }}>
                      ${fmt(row.currentPrice)}
                    </td>
                    <td style={{ padding: "6px 10px", textAlign: "right", color: pnlColor }}>
                      {row.unrealizedPnl >= 0 ? "+" : ""}${fmt(row.unrealizedPnl)}
                    </td>
                    <td style={{ padding: "6px 10px", textAlign: "right", color: pnlColor }}>
                      {row.pnlPct >= 0 ? "+" : ""}
                      {fmt(row.pnlPct)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
