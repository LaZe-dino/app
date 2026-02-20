const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

const WS_BASE = BASE_URL.replace(/^http/, 'ws') || 'ws://localhost:8000';

async function fetchAPI(endpoint: string, options?: RequestInit) {
  const url = `${BASE_URL}/api${endpoint}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error: ${res.status}`);
  }
  return res.json();
}

// ─── REST API ───────────────────────────────────────────────────────────────

export const api = {
  getDashboard: () => fetchAPI('/dashboard'),
  getMarketData: () => fetchAPI('/market-data'),
  getStockDetail: (symbol: string) => fetchAPI(`/market-data/${symbol}`),
  getTradeSignals: () => fetchAPI('/trade-signals'),
  analyzeStock: (symbol: string, analysis_type: string = 'comprehensive') =>
    fetchAPI('/research/analyze', {
      method: 'POST',
      body: JSON.stringify({ symbol, analysis_type }),
    }),
  deepAnalyze: (symbol: string) =>
    fetchAPI('/research/deep-analyze', {
      method: 'POST',
      body: JSON.stringify({ symbol }),
    }),
  getReports: () => fetchAPI('/research/reports'),
  getPortfolio: () => fetchAPI('/portfolio'),
  getRisk: () => fetchAPI('/risk'),
  getAgentsStatus: () => fetchAPI('/agents/status'),
  getSwarmEvents: (limit: number = 50) => fetchAPI(`/swarm/events?limit=${limit}`),
  getSwarmContext: (symbol: string) => fetchAPI(`/swarm/context/${symbol}`),
  getSwarmPrices: () => fetchAPI('/swarm/prices'),
  getSwarmSentiment: () => fetchAPI('/swarm/sentiment'),
  getSecFilings: (symbol: string, type: string = '10-K') =>
    fetchAPI(`/swarm/filings/${symbol}?filing_type=${type}`),
  ingestFilings: (symbol: string) =>
    fetchAPI(`/swarm/ingest/${symbol}`, { method: 'POST' }),
  getRiskGuardrail: () => fetchAPI('/swarm/risk'),
  getTheses: () => fetchAPI('/swarm/theses'),
  getMemoryStats: () => fetchAPI('/swarm/memory/stats'),
  queryMemory: (q: string, symbol?: string) =>
    fetchAPI(`/swarm/memory/query?q=${encodeURIComponent(q)}${symbol ? `&symbol=${symbol}` : ''}`),
  getQuantData: (symbol: string) => fetchAPI(`/swarm/quantitative/${symbol}`),
  getIngestionCache: () => fetchAPI('/swarm/ingestion/cache'),

  // HFT Engine
  getHFTStatus: () => fetchAPI('/hft/status'),
  getHFTDashboard: () => fetchAPI('/hft/dashboard'),
  getHFTOrderBook: (symbol: string) => fetchAPI(`/hft/orderbook/${symbol}`),
  getHFTOrderBooks: () => fetchAPI('/hft/orderbooks'),
  getHFTFpga: () => fetchAPI('/hft/fpga'),
  getHFTStrategies: () => fetchAPI('/hft/strategies'),
  getHFTRisk: () => fetchAPI('/hft/risk'),
  getHFTPositions: () => fetchAPI('/hft/positions'),
  getHFTExecution: () => fetchAPI('/hft/execution'),
  getHFTFills: (limit: number = 50) => fetchAPI(`/hft/fills?limit=${limit}`),
  getHFTMetrics: () => fetchAPI('/hft/metrics'),
  getHFTNetwork: () => fetchAPI('/hft/network'),
  getHFTFeedPrices: () => fetchAPI('/hft/feed/prices'),
  simulatePriceShock: (symbol: string, magnitude_pct: number) =>
    fetchAPI('/hft/simulate/price-shock', {
      method: 'POST',
      body: JSON.stringify({ symbol, magnitude_pct }),
    }),
};

// ─── WebSocket Manager ──────────────────────────────────────────────────────

type WSCallback = (data: any) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private listeners: Set<WSCallback> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 2000;
  private maxReconnectDelay = 30000;
  private currentDelay = 2000;
  private isActive = false;

  constructor(path: string) {
    this.url = `${WS_BASE}${path}`;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }
    this.isActive = true;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.currentDelay = this.reconnectDelay;
        console.log(`[WS] Connected: ${this.url}`);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.listeners.forEach(cb => cb(data));
        } catch {
          // ignore malformed messages
        }
      };

      this.ws.onclose = () => {
        if (this.isActive) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (!this.isActive) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.currentDelay);
    this.currentDelay = Math.min(this.currentDelay * 1.5, this.maxReconnectDelay);
  }

  subscribe(callback: WSCallback): () => void {
    this.listeners.add(callback);
    if (this.listeners.size === 1) {
      this.connect();
    }
    return () => {
      this.listeners.delete(callback);
      if (this.listeners.size === 0) {
        this.disconnect();
      }
    };
  }

  disconnect(): void {
    this.isActive = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const marketWS = new WebSocketManager('/ws/market');
export const swarmWS = new WebSocketManager('/ws/swarm');
export const hftWS = new WebSocketManager('/ws/hft');
