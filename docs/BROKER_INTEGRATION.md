# Broker Integration: Real Money & Third-Party APIs

This guide covers options to **deposit your own money** and **connect a real brokerage** so your bot can trade with real (or paper) funds.

---

## Overview: Three Paths

| Path | Best for | Deposit / funding | Trading |
|------|----------|-------------------|--------|
| **A. Alpaca Trading API** | You, single account, algo bot | Fund via Alpaca dashboard (ACH/wire) | API keys in app → bot places orders |
| **B. Alpaca Connect (OAuth)** | Let others connect their Alpaca account | Their Alpaca account | OAuth; user authorizes your app |
| **C. Alpaca Broker API** | You building a full brokerage product | Plaid ACH, instant funding | Multi-tenant; requires Alpaca partnership |

For **making this a reality with your own money**, **Path A** is the fastest: open an Alpaca account, fund it, add API keys to this app, and the bot trades that account.

---

## Option A: Alpaca Trading API (Your Own Account)

**Use case:** One person (you) trading your own Alpaca account via this app and bot.

### 1. Create an Alpaca account

- Sign up: [alpaca.markets](https://alpaca.markets)
- **Paper trading:** Free, instant. Use paper first to test.
- **Live trading:** Complete identity verification; then fund via ACH or wire in the Alpaca dashboard.

### 2. Get API keys

- **Paper:** Dashboard → API Keys → Generate → use **Paper** keys.
- **Live:** Same place, use **Live** keys (only after account approval).

Environments:

- Paper: `https://paper-api.alpaca.markets`
- Live: `https://api.alpaca.markets`

### 3. Add keys to this app

**Option 1 — Environment (recommended for single user / production)**  
In `backend/.env`:

```env
# Alpaca Trading API (your own account)
ALPACA_API_KEY_ID=PK...       # or live key
ALPACA_API_SECRET=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets   # or https://api.alpaca.markets for live
```

Restart the backend. The server will connect to Alpaca on startup.

**Option 2 — Connect from the app**  
You can also connect from the frontend (or any client) by calling:

- `POST /api/broker/connect` with body:  
  `{ "provider": "alpaca", "api_key_id": "...", "api_secret": "...", "paper": true }`

Keys are kept in memory only (cleared on restart). Use this for testing; for production, prefer env vars so secrets never touch the client.

Once connected (env or POST), the app uses the broker to:

- Read account (cash, equity, positions).
- Place/cancel orders when the arb bot (or other strategies) run.

### 4. Funding your account (your money)

- **Paper:** Default $100k; reset in dashboard if needed.
- **Live:** In Alpaca dashboard: **Funding** → link bank (ACH) or wire. No in-app deposit UI needed; you deposit on Alpaca’s site.

### 5. How the bot uses it

- If **broker is connected** (keys set): bot can submit real orders to Alpaca (paper or live).
- If **not connected**: bot runs in **simulation only** (in-memory P&L, no real orders).

So: deposit money in Alpaca → connect API keys in this app → bot trades that account.

---

## Option B: Alpaca Connect (OAuth) — Trade Using OAuth2 and Trading API

**Use case:** Users connect their Alpaca account via OAuth (no API keys in the app). Alpaca implements OAuth 2.0 so your app can access the Trading API on behalf of the user.

- User is redirected to Alpaca to log in and authorize your app.
- Alpaca returns an authorization code; your **backend** exchanges it for an access token.
- The token is used as `Authorization: Bearer <token>` for Trading API v2 (account, orders, positions).
- One token can authorize one paper and/or one live account; `env=paper` or `env=live` in the authorize URL.

**Requirements:**

- Register your app with Alpaca to get **client_id** and **client_secret**.
- Configure a **redirect_uri** (e.g. `https://your-backend.com/api/alpaca/oauth/callback`) in the Alpaca app settings.

**Backend env (optional):** In `backend/.env`:

```env
ALPACA_OAUTH_CLIENT_ID=your_oauth_client_id
ALPACA_OAUTH_CLIENT_SECRET=your_oauth_client_secret
ALPACA_OAUTH_REDIRECT_URI=https://your-backend.com/api/alpaca/oauth/callback
ALPACA_OAUTH_APP_SUCCESS_URL=myapp://alpaca
```

- **ALPACA_OAUTH_REDIRECT_URI** must match exactly what is whitelisted in the Alpaca dashboard.
- **ALPACA_OAUTH_APP_SUCCESS_URL** is where the backend redirects after a successful token exchange (e.g. your app deep link so the user returns to the app).

**Flow:**

1. **Get authorize URL:** `GET /api/alpaca/oauth/authorize?env=paper` (or `env=live`). Returns `{ "authorization_url": "https://app.alpaca.markets/oauth/authorize?..." }`.
2. **User authorizes:** Open that URL in a browser. User signs in at Alpaca and approves the app.
3. **Callback:** Alpaca redirects to your `redirect_uri` with `?code=...&state=...`. Your backend endpoint `GET /api/alpaca/oauth/callback` exchanges the code for an access token (server-side; client_secret is never exposed), sets the broker to an OAuth-based adapter, then redirects to `ALPACA_OAUTH_APP_SUCCESS_URL?connected=1&env=...`.
4. **Alternative (e.g. mobile):** If your app receives the `code` via a custom redirect (e.g. deep link that includes the code), call `POST /api/alpaca/oauth/token` with body `{ "code": "...", "redirect_uri": "...", "env": "paper" }`. Backend exchanges the code and sets the broker; response includes account info.

**Scopes used:** `account:write` and `trading` (place, cancel, modify orders).

**When to use:** When you want users to connect their own Alpaca account without pasting API keys (e.g. “Connect with Alpaca” in the app). For live trading by end users, Alpaca may require app review.

---

## Option C: Alpaca Broker API — Full Brokerage (Deposits + Multi-User)

**Use case:** You want to offer **accounts under your brand** and handle **deposits** (e.g. ACH) yourself.

- **Broker API** = create accounts per user, link banks (e.g. via **Plaid**), do ACH, instant funding (limits apply).
- Users “deposit” into an account your platform manages; Alpaca is the clearing broker.
- Requires **partnership/approval** with Alpaca.

**Deposits:**

- **Plaid:** User links bank in your UI → you get a processor token → Alpaca ACH relationship → transfers.
- **Instant funding:** Alpaca can give instant buying power (e.g. up to $1k) while ACH settles.

**When to use:** When you’re building a full brokerage product (multi-tenant, your own onboarding and deposits).

### Using Broker API in this app (sandbox)

If you have **Broker API** correspondent keys (from Alpaca Broker Dashboard), you can connect with **HTTP Basic auth** (key:secret). The app supports Broker API in addition to the Trading API.

**Environment (recommended):** In `backend/.env`:

```env
# Alpaca Broker API (correspondent; sandbox or live)
ALPACA_BROKER_API_KEY=your_broker_api_key
ALPACA_BROKER_API_SECRET=your_broker_api_secret
# Optional; default is sandbox
ALPACA_BROKER_BASE_URL=https://broker-api.sandbox.alpaca.markets
```

If both Broker API and Trading API env vars are set, **Broker API is used first**. Restart the backend after setting these.

**Connect from the app:**  
`POST /api/broker/connect` with body:

`{ "provider": "alpaca", "api_key_id": "...", "api_secret": "...", "use_broker_api": true }`

The app will use the first **ACTIVE** or **APPROVED** account returned by `GET /v1/accounts`. Place orders go to that account via `POST /v1/trading/accounts/{account_id}/orders`.

---

## Other Brokers (Beyond Alpaca)

| Broker | API | Deposit / connect | Notes |
|--------|-----|-------------------|--------|
| **Interactive Brokers (IBKR)** | TWS API / IBKR Gateway | Fund at IBKR; connect via API | Pro/inst; more assets; steeper setup |
| **TD Ameritrade / Schwab** | Developer API | Fund at broker | OAuth; good for US retail |
| **DriveWealth** | REST API | ACH via Plaid, etc. | White-label brokerage |
| **Plaid** | Plaid API | Not a broker; links banks | Use with Alpaca Broker API or others for ACH |

For “deposit my own money and trade with my bot,” **Alpaca Trading API (Option A)** is the simplest. For “let users deposit and trade,” you’d look at **Broker API + Plaid (Option C)** or a white-label partner.

---

## Security and Compliance

- **Never commit** live API keys. Use `.env` and keep it out of git.
- **Paper vs live:** Always test with paper keys first.
- **Regulation:** Offering trading/advice to others can require licenses (RIA, broker-dealer, etc.). Using Alpaca Trading API for **your own** account is typically personal use; offering the app to others can be different. Consult a compliance/legal advisor for your case.

---

## Summary: “I want to use my own money and my bot”

1. **Open an Alpaca account** (paper first).
2. **Fund it** (for live: ACH/wire in Alpaca dashboard).
3. **Add Alpaca API keys** to `backend/.env` as above.
4. **Restart backend**; in the app, “Broker” should show **Connected**.
5. **Start the arb bot**; it will use the connected broker (paper or live) when configured.

The code in this repo includes:

- **Broker adapters** (`backend/broker/`) — abstract interface, **Alpaca Trading API** (your account) and **Alpaca Broker API** (correspondent, multi-account).
- **Endpoints** — `GET /api/broker/status`, `POST /api/broker/connect`, `POST /api/broker/disconnect`.
- **Startup** — if `ALPACA_BROKER_API_KEY` and `ALPACA_BROKER_API_SECRET` are set, Broker API is used; else if `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET` are set, Trading API connects on startup.

**Next step (bot ↔ broker):** To have the arb bot (or other strategies) send **real orders** to your Alpaca account when the broker is connected, the strategy layer can call `get_broker().place_order(...)` when `get_broker()` is not None. Right now the bot runs in simulation (in-memory P&L); wiring it to the broker is the final step to trade your connected account.
