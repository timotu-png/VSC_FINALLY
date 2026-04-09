"use client";

import React, { useState } from "react";
import { SSEProvider } from "../contexts/SSEContext";
import { PortfolioProvider } from "../contexts/PortfolioContext";
import { WatchlistProvider } from "../contexts/WatchlistContext";
import Header from "../components/Header";
import WatchlistPanel from "../components/WatchlistPanel";
import MainChart from "../components/MainChart";
import PortfolioHeatmap from "../components/PortfolioHeatmap";
import PLChart from "../components/PLChart";
import PositionsTable from "../components/PositionsTable";
import TradeBar from "../components/TradeBar";
import ChatPanel from "../components/ChatPanel";

export default function TradingTerminal() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  return (
    <SSEProvider>
      <PortfolioProvider>
        <WatchlistProvider>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              height: "100vh",
              overflow: "hidden",
              backgroundColor: "#0d1117",
            }}
          >
            <Header />

            <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
              {/* Left: Watchlist */}
              <WatchlistPanel
                selectedTicker={selectedTicker}
                onSelectTicker={setSelectedTicker}
              />

              {/* Center: Main workspace */}
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  overflow: "hidden",
                  minWidth: 0,
                }}
              >
                {/* Top row: Main Chart + Heatmap */}
                <div
                  style={{
                    display: "flex",
                    flex: "0 0 42%",
                    minHeight: 0,
                    borderBottom: "1px solid #30363d",
                  }}
                >
                  <div
                    style={{
                      flex: "0 0 62%",
                      borderRight: "1px solid #30363d",
                      overflow: "hidden",
                    }}
                  >
                    <MainChart ticker={selectedTicker} />
                  </div>
                  <div style={{ flex: 1, overflow: "hidden" }}>
                    <PortfolioHeatmap />
                  </div>
                </div>

                {/* Middle: P&L Chart */}
                <div
                  style={{
                    flex: "0 0 22%",
                    borderBottom: "1px solid #30363d",
                    overflow: "hidden",
                  }}
                >
                  <PLChart />
                </div>

                {/* Bottom: Positions Table */}
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <PositionsTable />
                </div>

                {/* Trade Bar */}
                <TradeBar />
              </div>

              {/* Right: Chat Panel */}
              <ChatPanel />
            </div>
          </div>
        </WatchlistProvider>
      </PortfolioProvider>
    </SSEProvider>
  );
}
