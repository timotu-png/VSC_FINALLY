"use client";

import React from "react";
import { usePortfolio } from "../contexts/PortfolioContext";
import { useSSE } from "../contexts/SSEContext";

function fmt(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ConnectionDot({ status }: { status: number }) {
  const color = status === 1 ? "#3fb950" : status === 0 ? "#ecad0a" : "#f85149";
  const label = status === 1 ? "LIVE" : status === 0 ? "CONNECTING" : "OFFLINE";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          backgroundColor: color,
          boxShadow: `0 0 6px ${color}`,
        }}
      />
      <span style={{ fontSize: 11, color: color, letterSpacing: "0.05em" }}>{label}</span>
    </div>
  );
}

export default function Header() {
  const { portfolio } = usePortfolio();
  const { connectionStatus } = useSSE();

  const totalValue = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash_balance ?? 0;
  const pnl = portfolio?.unrealized_pnl ?? 0;
  const pnlColor = pnl >= 0 ? "#3fb950" : "#f85149";

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        height: 52,
        backgroundColor: "#161b22",
        borderBottom: "1px solid #30363d",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "#e6edf3", letterSpacing: "-0.02em" }}>
          Fin
        </span>
        <span style={{ fontSize: 20, fontWeight: 700, color: "#ecad0a", letterSpacing: "-0.02em" }}>
          Ally
        </span>
        <span
          style={{
            fontSize: 10,
            color: "#8b949e",
            marginLeft: 8,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}
        >
          AI Trading Workstation
        </span>
      </div>

      {/* Portfolio Value */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
        <div style={{ fontSize: 11, color: "#8b949e", letterSpacing: "0.05em" }}>
          PORTFOLIO VALUE
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#e6edf3", letterSpacing: "-0.02em" }}>
          ${fmt(totalValue)}
        </div>
        <div style={{ fontSize: 11, color: pnlColor }}>
          {pnl >= 0 ? "+" : ""}${fmt(pnl)} unrealized
        </div>
      </div>

      {/* Right side */}
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 10, color: "#8b949e", letterSpacing: "0.05em" }}>CASH</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#e6edf3" }}>${fmt(cash)}</div>
        </div>
        <ConnectionDot status={connectionStatus} />
      </div>
    </header>
  );
}
