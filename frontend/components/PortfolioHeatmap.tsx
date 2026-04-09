"use client";

import React, { useEffect, useRef } from "react";
import { usePortfolio } from "../contexts/PortfolioContext";
import { useSSE } from "../contexts/SSEContext";

function pnlColor(pct: number): string {
  const abs = Math.min(Math.abs(pct), 10) / 10;
  if (pct > 0) {
    const g = Math.round(80 + abs * 105);
    return `rgba(0, ${g}, 60, 0.85)`;
  } else if (pct < 0) {
    const r = Math.round(140 + abs * 108);
    return `rgba(${r}, 30, 30, 0.85)`;
  }
  return "rgba(40, 48, 58, 0.85)";
}

export default function PortfolioHeatmap() {
  const { portfolio } = usePortfolio();
  const { prices } = useSSE();
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!portfolio || portfolio.positions.length === 0) return;
    if (!svgRef.current || !containerRef.current) return;

    const { width, height } = containerRef.current.getBoundingClientRect();
    if (width === 0 || height === 0) return;

    import("d3-hierarchy").then(({ hierarchy, treemap, treemapSquarify }) => {
      const positions = portfolio.positions.map((p) => {
        const currentPrice = prices[p.ticker]?.price ?? p.current_price;
        const value = currentPrice * p.quantity;
        const pnl = ((currentPrice - p.avg_cost) / p.avg_cost) * 100;
        return { ticker: p.ticker, value, pnl };
      });

      const total = positions.reduce((s, p) => s + p.value, 0);
      if (total === 0) return;

      type LeafNode = { ticker: string; value: number; pnl: number };
      type RootNode = { children?: LeafNode[]; value?: number; ticker?: string; pnl?: number };

      const root = hierarchy<RootNode>({ children: positions })
        .sum((d) => d.value ?? 0)
        .sort((a, b) => (b.value || 0) - (a.value || 0));

      const tm = treemap<RootNode>()
        .size([width, height])
        .tile(treemapSquarify)
        .padding(2);

      tm(root);

      const svg = svgRef.current!;
      svg.setAttribute("width", String(width));
      svg.setAttribute("height", String(height));

      // Clear previous
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      root.leaves().forEach((leaf) => {
        const x0 = (leaf as unknown as { x0: number }).x0;
        const y0 = (leaf as unknown as { y0: number }).y0;
        const x1 = (leaf as unknown as { x1: number }).x1;
        const y1 = (leaf as unknown as { y1: number }).y1;
        const d = leaf.data as { ticker: string; pnl: number; value: number };

        const w = x1 - x0;
        const h = y1 - y0;
        if (w < 4 || h < 4) return;

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", String(x0));
        rect.setAttribute("y", String(y0));
        rect.setAttribute("width", String(w));
        rect.setAttribute("height", String(h));
        rect.setAttribute("fill", pnlColor(d.pnl));
        rect.setAttribute("stroke", "#0d1117");
        rect.setAttribute("stroke-width", "1");
        g.appendChild(rect);

        if (w > 30 && h > 20) {
          const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
          text.setAttribute("x", String(x0 + w / 2));
          text.setAttribute("y", String(y0 + h / 2 - (h > 36 ? 6 : 0)));
          text.setAttribute("text-anchor", "middle");
          text.setAttribute("dominant-baseline", "middle");
          text.setAttribute("fill", "#e6edf3");
          text.setAttribute("font-size", w > 60 ? "13" : "10");
          text.setAttribute("font-weight", "700");
          text.setAttribute("font-family", "monospace");
          text.textContent = d.ticker;
          g.appendChild(text);

          if (h > 36) {
            const pnlText = document.createElementNS("http://www.w3.org/2000/svg", "text");
            pnlText.setAttribute("x", String(x0 + w / 2));
            pnlText.setAttribute("y", String(y0 + h / 2 + 10));
            pnlText.setAttribute("text-anchor", "middle");
            pnlText.setAttribute("dominant-baseline", "middle");
            pnlText.setAttribute("fill", d.pnl >= 0 ? "#3fb950" : "#f85149");
            pnlText.setAttribute("font-size", "10");
            pnlText.setAttribute("font-family", "monospace");
            pnlText.textContent = `${d.pnl >= 0 ? "+" : ""}${d.pnl.toFixed(1)}%`;
            g.appendChild(pnlText);
          }
        }

        svg.appendChild(g);
      });
    });
  }, [portfolio, prices]);

  const hasPositions = portfolio && portfolio.positions.length > 0;

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
        Portfolio Heatmap
      </div>
      <div ref={containerRef} style={{ flex: 1, position: "relative", minHeight: 0 }}>
        {hasPositions ? (
          <svg ref={svgRef} style={{ position: "absolute", top: 0, left: 0 }} />
        ) : (
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
            No positions
          </div>
        )}
      </div>
    </div>
  );
}
