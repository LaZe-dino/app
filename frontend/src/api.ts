const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

const WS_BASE = BASE_URL.replace(/^http/, 'ws') || 'ws://localhost:8000';

// ─── Auth Token Management ──────────────────────────────────────────────────

let _authToken: string | null = null;
let _authPromise: Promise<void> | null = null;

const DEFAULT_EMAIL = 'demo@hedgefund.ai';
const DEFAULT_PASSWORD = 'demo123456';
const DEFAULT_NAME = 'Demo Trader';

async function ensureAuth(): Promise<string> {
  if (_authToken) return _authToken;

  if (!_authPromise) {
    _authPromise = (async () => {
      try {
        const loginRes = await fetch(`${BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: DEFAULT_EMAIL, password: DEFAULT_PASSWORD }),
        });

        if (loginRes.ok) {
          const data = await loginRes.json();
          _authToken = data.token;
          return;
        }

        const regRes = await fetch(`${BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: DEFAULT_EMAIL,
            password: DEFAULT_PASSWORD,
            display_name: DEFAULT_NAME,
          }),
        });

        if (regRes.ok) {
          const data = await regRes.json();
          _authToken = data.token;
          return;
        }

        console.error('Auth failed:', await regRes.text());
      } catch (e) {
        console.error('Auth error:', e);
      }
    })();
  }

  await _authPromise;
  return _authToken || '';
}

async function fetchAPI(endpoint: string, options?: RequestInit) {
  const token = await ensureAuth();
  const url = `${BASE_URL}/api${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      _authToken = null;
      _authPromise = null;
    }
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

  // Real Stock Data (Yahoo Finance)
  getStockQuote: (symbol: string) => fetchAPI(`/stock/${symbol}/quote`),
  getStockChart: (symbol: string, range: string = '1D') =>
    fetchAPI(`/stock/${symbol}/chart?range=${range}`),
  getBatchQuotes: (symbols: string[]) =>
    fetchAPI(`/stocks/batch?symbols=${symbols.join(',')}`),

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
  getHFTRealtimePrices: () => fetchAPI('/hft/realtime-prices'),
  simulatePriceShock: (symbol: string, magnitude_pct: number) =>
    fetchAPI('/hft/simulate/price-shock', {
      method: 'POST',
      body: JSON.stringify({ symbol, magnitude_pct }),
    }),

  // Arbitrage Bot
  startBot: (budget?: number) => fetchAPI('/bot/start', {
    method: 'POST',
    body: JSON.stringify(budget ? { budget } : {}),
  }),
  stopBot: () => fetchAPI('/bot/stop', { method: 'POST' }),
  getBotStatus: () => fetchAPI('/bot/status'),
  getBotTrades: (limit: number = 50) => fetchAPI(`/bot/trades?limit=${limit}`),
  getBotPnl: () => fetchAPI('/bot/pnl'),
  getBotWallet: () => fetchAPI('/bot/wallet'),
  depositToWallet: (amount: number) =>
    fetchAPI('/bot/wallet/deposit', { method: 'POST', body: JSON.stringify({ amount }) }),
  withdrawFromWallet: (amount: number) =>
    fetchAPI('/bot/wallet/withdraw', { method: 'POST', body: JSON.stringify({ amount }) }),

  // Broker (Alpaca — connect your account for real/paper trading)
  getBrokerStatus: () => fetchAPI('/broker/status'),
  connectBroker: (apiKeyId: string, apiSecret: string, paper: boolean = true, useBrokerApi: boolean = false) =>
    fetchAPI('/broker/connect', {
      method: 'POST',
      body: JSON.stringify({ provider: 'alpaca', api_key_id: apiKeyId, api_secret: apiSecret, paper, use_broker_api: useBrokerApi }),
    }),
  disconnectBroker: () =>
    fetchAPI('/broker/disconnect', { method: 'POST' }),
  placeBrokerOrder: (params: {
    symbol: string;
    side: 'buy' | 'sell';
    qty: number;
    order_type?: 'market' | 'limit';
    limit_price?: number;
    time_in_force?: string;
  }) =>
    fetchAPI('/broker/order', {
      method: 'POST',
      body: JSON.stringify({
        symbol: params.symbol,
        side: params.side,
        qty: params.qty,
        order_type: params.order_type ?? 'limit',
        limit_price: params.limit_price,
        time_in_force: params.time_in_force ?? 'day',
      }),
    }),

  // Alpaca OAuth2 (Connect on behalf of user — no API keys; user authorizes in browser)
  // Uses backend URL with fallback so OAuth works when EXPO_PUBLIC_BACKEND_URL is unset (e.g. local dev)
  getAlpacaOAuthAuthorizeUrl: async (env: 'paper' | 'live' = 'paper') => {
    const base = (typeof process !== 'undefined' && process.env?.EXPO_PUBLIC_BACKEND_URL) || 'http://localhost:8000';
    const url = `${base}/api/alpaca/oauth/authorize?env=${env}`;
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json' } });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Failed to get OAuth URL: ${res.status}`);
    }
    return res.json() as Promise<{ authorization_url: string; state?: string; env?: string }>;
  },
  exchangeAlpacaOAuthCode: (code: string, redirectUri: string, env: 'paper' | 'live' = 'paper') =>
    fetchAPI('/alpaca/oauth/token', {
      method: 'POST',
      body: JSON.stringify({ code, redirect_uri: redirectUri, env }),
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
