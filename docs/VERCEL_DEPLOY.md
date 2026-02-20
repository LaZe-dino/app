# Deploy to Vercel and Fix “Old Build” / “No API” Issues

## Why it looks the same / API doesn’t work

1. **Old build** – Vercel may be building from an old Git commit or using a cached build.
2. **No API/data** – The serverless function must receive the correct path; the frontend must call the same origin on Vercel.

## Step 1: Push your latest code to GitHub

From the **project folder** (the one that contains `api/` and `frontend/`):

```powershell
cd "C:\Users\adity\OneDrive\Desktop\server\app-main\app-main"
git add -A
git status
git commit -m "Fix Vercel API path and deploy"   # if there are changes
git push origin master:main
```

Use `git push origin main` if your branch is already `main`.

## Step 2: Vercel project settings

1. Open **Vercel Dashboard** → your project → **Settings** → **General**.
2. **Root Directory**: leave **empty** (or set to `.`).  
   The root must be the repo root so both `api/` and `frontend/` are used.  
   If Root Directory is set to `frontend`, only the frontend is built and the API is ignored.
3. **Framework Preset**: leave as **Other** (build is controlled by `vercel.json`).

## Step 3: Environment variables

In **Settings** → **Environment Variables**, add at least:

| Name | Value | Notes |
|------|--------|--------|
| `JWT_SECRET` | (any long random string) | Required for auth |
| `SUPABASE_URL` | Your Supabase project URL | From Supabase dashboard |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key | From Supabase dashboard |

Do **not** set `EXPO_PUBLIC_BACKEND_URL` for the Vercel deployment.  
Leaving it unset makes the frontend call `/api/...` on the same domain (your Vercel URL), so the API is used correctly.

## Step 4: Redeploy with cache cleared

1. Go to **Deployments**.
2. Open the **⋯** menu on the latest deployment.
3. Choose **Redeploy**.
4. Check **“Clear build cache and redeploy”**.
5. Click **Redeploy**.

This forces a new build from the latest commit and avoids old cached output.

## Step 5: Confirm after deploy

- Open your Vercel URL (e.g. `https://atcapital-phi.vercel.app`).
- Open browser DevTools (F12) → **Network**.
- Use the app (e.g. open dashboard, run an analysis).
- You should see requests to `https://your-app.vercel.app/api/...` (same origin). If they return 200, the API is working.
- If you see 401, 500, or “Failed to fetch”, check **Vercel** → **Functions** / **Logs** for the `/api/index` function errors.

## Summary checklist

- [ ] Latest code pushed to GitHub (`master` or `main`).
- [ ] Vercel **Root Directory** is empty (or `.`).
- [ ] Env vars set: `JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
- [ ] Redeploy with **“Clear build cache and redeploy”**.
- [ ] Test the app and check Network tab + Vercel function logs.
