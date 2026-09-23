# MANJI — Tools & Services: What We Use and Why

Last updated: 2026-09-23. Status: production (free-tier-first).

Rule: prefer managed free tiers with no credit card; avoid vendor-specific code so any row below can be swapped via env vars.

## 1. Backend hosting — Render (Docker, free tier)

Chosen: **Render Web Service** (Oregon, Docker, `manji-api.onrender.com`).

| Alternative | Why not |
|---|---|
| Railway | Free trial credits expire; unpredictable руку sleep behavior; less generous free Postgres. |
| Fly.io | Powerful but requires card for signup in many regions; steeper ops learning curve. |
| Heroku | No free tier anymore; cheapest dyno + Postgres ≈ $12+/mo. |
| AWS EC2 / DigitalOcean droplet | Full control but we manage OS, patches, TLS, deploys ourselves; ~$5–6/mo minimum. |
| Vercel / Netlify Functions | Great for frontend/serverless, poor fit for long-running Django + gunicorn + background threads. |

Why Render won: native Dockerfile support, auto-deploy on git push, free tier (sleeps when idle — acceptable for launch), health-check path support, env-var management in dashboard.

Swap path: any Docker host works (`Dockerfile` + `start.sh` are portable). Move by pointing DNS + `DATABASE_URL`/`REDIS_URL` at the same Neon/Upstash instances.

## 2. Frontend & download site — Cloudflare (Workers/Pages)

Chosen: **Cloudflare Workers/Pages** (`manji-download.olatunjie335.workers.dev`, custom domain later).

| Alternative | Why not |
|---|---|
| Vercel | Excellent DX, but bandwidth/function limits on hobby tier; overkill for a single static page. |
| Netlify | Similar to Vercel; free tier fine, but we already use Cloudflare for DNS — one fewer vendor. |
| GitHub Pages | Free and simple, but no preview URLs per commit, weaker caching control,长时间 build queues. |
| Render Static Site | Works, but ties frontend to the same vendor/outage domain as the backend. |

Why Cloudflare won: already our DNS, huge free tier, global edge caching, instant static deploys, preview URLs. The download site is a single `index.html` with zero build step.

## 3. Database — Neon (serverless Postgres, free tier)

Chosen: **Neon** (AWS US East 2 / Ohio, 0.5 GB free, scales to zero).

| Alternative | Why not |
|---|---|
| Supabase Postgres | Good, but we use Supabase for storage; keeping DB on Neon spreads risk and Neon’s branching/autoscale-to-zero fits our budget better. |
| Railway Postgres | Ephemeral free credits; costs ramp fast. |
| Render Postgres | Cheapest paid instance ≈ $6/mo; free tier was retired/limited. |
| AWS RDS | Minimum ~$12/mo + ops overhead; unjustifiable at launch. |
| SQLite | Fine for dev, unusable for a multi-user production API. |

Why Neon won: real Postgres over a standard connection string (`DATABASE_URL`), free tier with autoscale-to-zero, branching for safe migration tests, US region close to Render (Oregon) and Upstash (Ohio).

Swap path: change `DATABASE_URL` only — Django ORM is provider-agnostic.

## 4. Cache / rate limits — Upstash Redis (free tier)

Chosen: **Upstash Redis** (Ohio, TLS, `rediss://`).

| Alternative | Why not |
|---|---|
| Render Redis | Paid on current plans; no usable free tier. |
| Redis Cloud (redis.io) | 30 MB free is fine, but Upstash’s REST + TCP options and generous request quota fit better. |
| Dragonfly / self-hosted | Extra ops burden for zero gain at our scale. |
| No cache at all | JWT throttling and AI quotas need a shared store across gunicorn workers. |

Why Upstash won: free tier (10k commands/day, 256 MB), TLS out of the box, Ohio region next to Neon, works with `django-redis` over standard `REDIS_URL`.

Swap path: change `REDIS_URL` only.

## 5. Media / file storage — Supabase Storage (S3-compatible API)

Chosen: **Supabase Storage**, bucket `manji-media` (private), via S3 API + `django-storages`.

| Alternative | Why not |
|---|---|
| **Cloudflare R2** | Zero-egress pricing is attractive, but requires a **credit card on file even for the free tier** — a hard blocker. Revisit when a card is available. |
| **Cloudinary** | Great image CDN/transformations, but free tier is image-centric with tight transformation quotas; our needs are generic files (video, audio, project files), not just images. Vendor-specific SDK instead of standard S3. |
| AWS S3 | Needs a card; ~$0.023/GB + request fees; CloudFront setup overhead. Revisit at scale. |
| Uploadcare / Upload.io | Per-upload pricing; unnecessary while Supabase covers us. |
| Local disk on Render | Free-tier disks are ephemeral; uploads vanish on every deploy. Never for production. |

Why Supabase won: no card required, S3-compatible API (no vendor lock-in — same `django-storages` backend as AWS/R2), private buckets with signed URLs (`AWS_QUERYSTRING_AUTH=True`), generous free storage.

Swap path: change `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_ENDPOINT_URL` / `AWS_STORAGE_BUCKET_NAME`. Code stays identical for R2 or AWS S3 later.

## 6. Transactional email — Gmail API (OAuth2) with SMTP fallback

Chosen: **Gmail API** (`gmail.send` scope, OAuth2 refresh-token flow, `apps/core/gmail_service.py`), falling back to Django SMTP backend.

| Alternative | Why not |
|---|---|
| SendGrid (SMTP) | Still configured as fallback, but free tier is 100 emails/day and deliverability setup (SPF/DKIM) is extra work; Gmail API sends from our real mailbox with zero DNS setup. |
| Mailgun / Resend / Postmark | Excellent APIs, but all need a card or domain verification steps; Resend’s free tier is generous — closest runner-up if Gmail OAuth ever breaks. |
| Raw SMTP via Gmail (app password) | Google is phasing out less-secure/app-password flows; OAuth2 refresh tokens are the supported path. |
| Console backend only | Dev-only; users would never receive password resets. |

Why Gmail API won: no card, no new vendor, sends from our own address, OAuth2 refresh tokens don’t expire on password change, and the code degrades gracefully to SMTP if unconfigured.

Swap path: `send_email()` in `apps/core/email_utils.py` tries Gmail first, then Django `send_mail` — set `EMAIL_HOST*` vars to switch providers without code changes.

## 7. CI/CD + installer distribution — GitHub Actions + GitHub Releases

Chosen: **GitHub Actions** (`windows-latest` runner) building NSIS + portable `.exe`, attached to **GitHub Releases**.

| Alternative | Why not |
|---|---|
| CircleCI / Travis / AppVeyor | Another vendor + secrets to manage; GitHub Actions minutes are free for public repos and already integrated. |
| Self-hosted builder | A Windows VM we maintain — fragile and unnecessary. |
| Hosting `.exe` on S3/R2 | Pay egress; lose version history, checksums UX, and auto-generated changelogs that Releases gives free. |
| Microsoft Store / Winget | Great later for trust/SmartScreen, but review pipelines and certs slow down v1.0. Submit after traction. |

Why GitHub won: free Windows runners, artifacts attach to versioned releases with SHA256, the download site reads the Releases API live (no redeploy per release), and `electron-updater` can point at Releases for auto-updates later.

## 8. Desktop wrapper — Electron + electron-builder

Chosen: **Electron** (`electron/main.cjs`, `preload.cjs`) packaged with **electron-builder** (NSIS installer + portable).

| Alternative | Why not |
|---|---|
| Tauri | Smaller binaries and Rust performance are tempting, but our frontend is React + heavy Canvas work already tuned for Chromium; rewriting the shell integration isn’t worth it pre-launch. Revisit for v2 if installer size (~70 MB) hurts. |
| NW.js | Smaller community, weaker auto-update story than electron-builder + GitHub Releases. |
| PWA / browser-only | No file-system access, no installer presence, weaker story for an “animation studio” product on Windows. |
| MSIX packaging | Store-only benefits; NSIS reaches users directly today. |

Why Electron won: existing React app runs unmodified, `preload.cjs` securely bridges `MANJI_API_URL` per environment, NSIS gives Start Menu/uninstaller/upgrade semantics Windows users expect.

## 9. DNS / CDN / TLS — Cloudflare

Chosen: **Cloudflare** (DNS, edge cache, automatic HTTPS).

| Alternative | Why not |
|---|---|
| Route53 + CloudFront | Pay-per-query + certificate management overhead. |
| Registrar DNS only | No caching, no DDoS protection, manual TLS. |

## 10. Auth — Django + SimpleJWT (self-built, no vendor)

Chosen: **Custom `users.User` + djangorestframework-simplejwt** (access/refresh, blacklist on logout).

| Alternative | Why not |
|---|---|
| Clerk / Auth0 | Per-user pricing; external dependency for the most critical path; migration pain later. |
| Supabase Auth / Neon Auth | We use those vendors for storage/DB only; auth stays in Django so permissions (`is_creator`, `is_admin`, official-content guards) live next to the models they protect. |
| Firebase Auth | Google lock-in; token verification adds latency to every request. |

## 11. AI providers — abstraction with fallback chain

Chosen: **provider abstraction** (`apps/ai/providers.py`): Gemini primary, OpenRouter fallback, configurable via `AI_CHAT_PROVIDER` / `AI_CHAT_FALLBACK_PROVIDER`. Image gen: DALL-E / Stability / Leonardo / local placeholder.

No single-vendor lock-in by design: every feature calls the `ChatProvider` interface, so swapping vendors is an env-var change.

---

## One-line summary

Render runs it · Cloudflare serves it · Neon stores rows · Upstash stores cache · Supabase stores files · Gmail sends mail · GitHub builds + ships the installer · Django owns auth · AI is provider-agnostic.
