"use client";

import React, { useEffect, useRef, useState } from "react";
import type { ChatMessage, ChatAction } from "../types";

function ActionLine({ action }: { action: ChatAction }) {
  const ok = action.status === "success";
  let desc = "";
  if (action.type === "trade") {
    const p = action.payload as { side?: string; quantity?: number; ticker?: string; price?: number };
    if (ok) {
      desc = `${p.side === "buy" ? "Bought" : "Sold"} ${p.quantity} ${p.ticker}${p.price ? ` @ $${p.price.toFixed(2)}` : ""}`;
    } else {
      desc = `Trade ${p.ticker} failed: ${action.error || "error"}`;
    }
  } else if (action.type === "watchlist") {
    const p = action.payload as { action?: string; ticker?: string };
    if (ok) {
      desc = `${p.action === "add" ? "Added" : "Removed"} ${p.ticker} ${p.action === "add" ? "to" : "from"} watchlist`;
    } else {
      desc = `Watchlist ${p.ticker} failed: ${action.error || "error"}`;
    }
  }
  return (
    <div
      style={{
        fontSize: 10,
        color: ok ? "#3fb950" : "#f85149",
        padding: "2px 0",
        display: "flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      <span>{ok ? "✓" : "⚠"}</span>
      <span>{desc}</span>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        marginBottom: 10,
      }}
    >
      <div
        style={{
          maxWidth: "85%",
          padding: "8px 10px",
          borderRadius: isUser ? "10px 10px 2px 10px" : "10px 10px 10px 2px",
          backgroundColor: isUser ? "#1a3a5c" : "#1c2128",
          border: `1px solid ${isUser ? "#2a5a8c" : "#30363d"}`,
          fontSize: 12,
          color: "#e6edf3",
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {msg.content}
      </div>
      {msg.actions && msg.actions.length > 0 && (
        <div style={{ maxWidth: "85%", padding: "2px 2px 0" }}>
          {msg.actions.map((a, i) => (
            <ActionLine key={i} action={a} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatPanel() {
  const [open, setOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.message || "(no response)",
        actions: data.actions || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "⚠ Connection error. Please try again.",
          actions: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const toggleBtn = (
    <button
      onClick={() => setOpen((o) => !o)}
      style={{
        position: "absolute",
        left: -28,
        top: "50%",
        transform: "translateY(-50%)",
        width: 28,
        height: 48,
        backgroundColor: "#161b22",
        border: "1px solid #30363d",
        borderRight: "none",
        color: "#8b949e",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 10,
        borderRadius: "4px 0 0 4px",
        writingMode: "vertical-rl",
        letterSpacing: "0.08em",
        padding: "4px 2px",
        zIndex: 20,
      }}
    >
      {open ? "▶ AI" : "◀ AI"}
    </button>
  );

  return (
    <div
      style={{
        position: "relative",
        width: open ? 300 : 0,
        flexShrink: 0,
        overflow: "visible",
        transition: "width 0.2s ease",
      }}
    >
      {toggleBtn}
      {open && (
        <div
          style={{
            width: 300,
            height: "100%",
            backgroundColor: "#161b22",
            borderLeft: "1px solid #30363d",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "8px 12px",
              borderBottom: "1px solid #30363d",
              fontSize: 10,
              color: "#8b949e",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ color: "#ecad0a" }}>●</span> AI Assistant
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "10px",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {messages.length === 0 && (
              <div style={{ color: "#484f58", fontSize: 12, textAlign: "center", marginTop: 20 }}>
                Ask me about your portfolio, request analysis, or say{" "}
                <span style={{ color: "#8b949e" }}>&ldquo;buy 5 AAPL&rdquo;</span>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {loading && (
              <div style={{ display: "flex", gap: 4, padding: "4px 0" }}>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: "#8b949e",
                      animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                    }}
                  />
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div
            style={{
              padding: "8px 10px",
              borderTop: "1px solid #30363d",
              flexShrink: 0,
              display: "flex",
              gap: 6,
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask FinAlly..."
              rows={2}
              style={{
                flex: 1,
                background: "#1c2128",
                border: "1px solid #30363d",
                color: "#e6edf3",
                padding: "6px 8px",
                fontSize: 12,
                borderRadius: 4,
                resize: "none",
                outline: "none",
                fontFamily: "monospace",
                lineHeight: 1.4,
              }}
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? "#30363d" : "#753991",
                border: "none",
                color: loading || !input.trim() ? "#484f58" : "#fff",
                padding: "6px 10px",
                borderRadius: 4,
                cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                fontSize: 13,
                alignSelf: "flex-end",
                transition: "background 0.1s",
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
