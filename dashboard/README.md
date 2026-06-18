# InvestAI Dashboard 📈

A mobile-first **PWA** that shows today's InvestAI calls at a glance. Reads
**live from Notion** (the same Recommendations + Daily Review databases the
daily agent writes to). Gated by a **shared passcode**.

What you see:

- **Strategy P&L (paper)** — return if you followed every graded BUY (and shorted SELLs)
- **Accuracy** (latest) + **7-day average** + 🔥 streak
- **Self-rating** and **best-read stock**
- **Accuracy trend** line chart
- **Buy today** / **Sell-or-avoid today** lists
- **Yesterday's calls** with graded outcomes (✓ / ✗) and actual move %

---

## 1. One-time Notion setup

1. Go to <https://www.notion.so/my-integrations> → **New integration**
   (internal). Copy the **Internal Integration Secret** (`secret_…`).
2. Open the **INVESTAI** page in Notion → **•••** → **Connections** →
   add your integration. (This grants it read access to both databases.)

The two data-source IDs are already known and pre-filled in
`.env.local.example`:

| Database        | Data source ID                          |
| --------------- | --------------------------------------- |
| Recommendations | `8f225b65-31b3-4f12-9700-34e7a2a459e0`  |
| Daily Review    | `a69929f7-e386-4d9a-bf60-16f468dd4325`  |

## 2. Configure environment

```bash
cp .env.local.example .env.local
```

Fill in:

- `NOTION_TOKEN` — the `secret_…` from step 1
- `DASHBOARD_PASSCODE` — the password you'll share with trusted people
- `DASHBOARD_SESSION_SECRET` — a long random string:
  ```bash
  node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
  ```

## 3. Run locally

```bash
npm install
npm run dev
```

Open <http://localhost:3000>, enter the passcode.

## 4. Deploy to Vercel (free)

```bash
npm i -g vercel        # if you don't have it
vercel                 # link/create the project
vercel --prod          # deploy
```

Then in the Vercel dashboard → **Settings → Environment Variables**, add the
same four variables from `.env.local`. Redeploy.

You'll get a URL like `https://investai-xxxx.vercel.app`.

## 5. Install on your phone (home-screen app)

- **iPhone (Safari):** open the URL → Share → **Add to Home Screen**
- **Android (Chrome):** open the URL → menu → **Install app**

It launches full-screen with its own icon — feels native, no App Store.

---

## How it works

```
Phone (PWA)  →  Next.js server (Vercel)  →  Notion REST API
                       │                        ├─ Recommendations
                  passcode gate                 └─ Daily Review
```

- `lib/notion.ts` — queries both data sources, paginates, computes KPIs. The
  Notion token lives only server-side; the browser never sees it.
- `middleware.ts` + `app/api/login` — passcode → session cookie.
- `app/page.tsx` — server component, `force-dynamic` so every load is fresh.
- `app/AccuracyChart.tsx` — dependency-free SVG line chart.

## "Today" / "Yesterday" logic

The dashboard does **not** rely on the device clock. It reads the two most
recent distinct `Date` values present in Recommendations: the newest is
"today", the one before it is "yesterday". So it always shows the latest run,
even before/after the 08:30 IST agent run.

## Upgrading the sign-in later

Today it's a shared passcode. To move to per-person Google sign-in with an
email allowlist, swap `middleware.ts` + `app/api/login` for Auth.js
(NextAuth) with a Google provider and an `allowedEmails` check. The rest of
the app is unchanged.
