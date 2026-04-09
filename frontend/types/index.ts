export interface PriceEntry {
  ticker: string;
  price: number;
  timestamp: number;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percent: number;
}

export interface Portfolio {
  positions: Position[];
  cash_balance: number;
  total_value: number;
  unrealized_pnl: number;
}

export interface WatchlistEntry {
  ticker: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
}

export interface ChatAction {
  type: "trade" | "watchlist";
  payload: Record<string, unknown>;
  status: "success" | "error";
  error: string | null;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface TradeError {
  code: string;
  message: string;
}
