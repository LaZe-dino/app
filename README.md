# Here are your Instructions

## Run the bot with Alpaca (live or paper)

1. **Connect Alpaca**: In the app go to **HFT → Wallet**. Connect via API keys (from alpaca.markets) or **Connect with Alpaca (OAuth)**. Paper or live is your choice.
2. **Start the bot**: Go to **HFT → Arb Bot**. Set your trading budget, then tap **Run bot with Alpaca** (or "Start bot" if not connected — sim only). One button; when Alpaca is connected, the bot sends real limit orders.
3. **Manual trades**: On any stock screen, tap **Trade** to place buy/sell orders with your connected Alpaca account.

**OAuth note**: If using OAuth, your backend must be publicly accessible (not localhost). Use **ngrok** for local dev (`ngrok http 8000`) or deploy to Vercel/Railway. See `docs/ALPACA_OAUTH_SETUP.md` for details. **API keys work with localhost** — no deployment needed.

## Deploying to Vercel

1. **Root Directory** (required): In Vercel → Settings → General, set **Root Directory** to the folder that contains **both** `api/` and `frontend/` (and `vercel.json`). Do **not** set it to `frontend` only—then the `api` folder is missing and you get "pattern doesn't match any Serverless Functions". Use the parent folder (e.g. `app-main` if your app lives there) or leave empty if the repo root has `api/` and `frontend/`.
2. **Environment variables**: Add your env vars (e.g. `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `JWT_SECRET`) in Vercel → Settings → Environment Variables.
3. Deploy; the build will export the Expo web app and deploy the Python API under `/api/*`.
