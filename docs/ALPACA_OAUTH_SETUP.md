# Alpaca OAuth Setup Guide

## The Problem: Localhost Won't Work

Alpaca OAuth requires a **publicly accessible redirect URI**. If your backend runs on `localhost:8000`, Alpaca **cannot** redirect back to it because `localhost` is only accessible on your computer.

## Solutions

### Option 1: Use ngrok (Easiest for Local Dev)

**ngrok** creates a public tunnel to your localhost backend.

1. **Install ngrok**: Download from [ngrok.com](https://ngrok.com/download) or `brew install ngrok` / `choco install ngrok`

2. **Start your backend**:
   ```bash
   cd backend
   uvicorn server:app --reload --port 8000
   ```

3. **In a new terminal, start ngrok**:
   ```bash
   ngrok http 8000
   ```

4. **Copy the HTTPS URL** ngrok gives you (e.g. `https://abc123.ngrok-free.app`)

5. **Update your `.env`**:
   ```env
   ALPACA_OAUTH_REDIRECT_URI=https://abc123.ngrok-free.app/api/alpaca/oauth/callback
   ALPACA_OAUTH_APP_SUCCESS_URL=exp://localhost:8081/--/alpaca
   ```

6. **In Alpaca Dashboard**:
   - Go to your OAuth app settings
   - Add **exactly** this redirect URI: `https://abc123.ngrok-free.app/api/alpaca/oauth/callback`
   - Save

7. **Restart your backend** (so it loads the new `.env`)

8. **Try OAuth again** in the app — it should work!

**Note**: ngrok URLs change each time you restart ngrok (unless you have a paid plan with a fixed domain). So you'll need to update `.env` and Alpaca dashboard each time.

---

### Option 2: Deploy Your Backend (Production)

Deploy your backend to **Vercel**, **Railway**, **Render**, or any hosting that gives you a public URL.

1. **Deploy** your backend (e.g. to Vercel)

2. **Get your public URL** (e.g. `https://your-api.vercel.app`)

3. **Set environment variables** in your hosting platform:
   ```env
   ALPACA_OAUTH_CLIENT_ID=9c341d4847bae44d2c98525253ce2c88
   ALPACA_OAUTH_CLIENT_SECRET=886b1cf85571941f9c2d91cd8e4ef23365fb8ec2
   ALPACA_OAUTH_REDIRECT_URI=https://your-api.vercel.app/api/alpaca/oauth/callback
   ALPACA_OAUTH_APP_SUCCESS_URL=exp://localhost:8081/--/alpaca
   ```

4. **In Alpaca Dashboard**:
   - Add redirect URI: `https://your-api.vercel.app/api/alpaca/oauth/callback`
   - Save

5. **Try OAuth** — it will work because Alpaca can reach your deployed backend.

---

### Option 3: Use API Keys Instead (No OAuth Needed)

If you don't want to deal with OAuth redirect URIs:

1. Go to **HFT → Wallet** in the app
2. Enter your **API Key ID** and **API Secret** from alpaca.markets
3. Tap **Connect Alpaca (API keys)**
4. Done — no OAuth, no redirect URI, no deployment needed.

---

## Quick Checklist

- [ ] Backend is running (or deployed)
- [ ] `ALPACA_OAUTH_REDIRECT_URI` in `.env` is a **public URL** (not localhost)
- [ ] Same redirect URI is added in **Alpaca Dashboard → Your OAuth App → Redirect URIs**
- [ ] Backend restarted after changing `.env`
- [ ] Try "Connect with Alpaca (OAuth)" in the app

---

## Troubleshooting

**"OAuth not configured"**
- Check `ALPACA_OAUTH_CLIENT_ID` and `ALPACA_OAUTH_REDIRECT_URI` are set in `.env`
- Restart backend after changing `.env`

**"localhost detected" warning**
- Your redirect URI is `localhost` — Alpaca can't reach it
- Use ngrok (Option 1) or deploy (Option 2)

**"Token exchange failed"**
- Redirect URI mismatch: check `.env` matches exactly what's in Alpaca dashboard
- Client secret might be wrong
- Check backend logs for the exact error

**"Account not accessible"**
- Token might be expired or invalid
- Try disconnecting and reconnecting
- Check you're using the right env (paper vs live)
