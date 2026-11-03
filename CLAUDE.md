# CLAUDE.md — Saudi Property Portal

This file tells Claude how to work on this codebase. Read it fully before making changes.

## 1. What we are building

A REGA-licensed property listings portal for Saudi Arabia, similar to Bayut.sa, starting with an MVP.
- **Buyers and renters** search sale and rent listings, view them on a map and contact brokers.
- **Brokers, agencies and owners** post listings that carry a REGA ad licence. Brokers pay for visibility through a prepaid **credits wallet**.
- **Launch market:** Eastern Province (Dammam, Khobar, Dhahran, Jubail). Riyadh and Jeddah come later.
- **Brand name:** not decided yet. Use the placeholder `PORTAL_NAME` from settings/env. Never hard-code a name.

**Owner:** Mohammed Bilal (Codesudio). He is not a full-time developer, so:
- Explain what you changed and why, in plain language, after each task.
- Prefer simple, conventional, well-documented solutions over clever ones.
- Give the exact commands to run (Docker Desktop on Windows/macOS) whenever an action is needed.
- Never leave the project in a broken state. Run the checks in §9 before saying a task is done.

## 2. Non-negotiable rules (REGA / Saudi compliance)

These come from REGA's Real Estate Marketing and Advertising Regulation (May 2026). Every feature must respect them.
1. **Hosting in KSA.** In production, every server, database and file bucket runs in an Oracle Cloud Saudi region (Jeddah or Riyadh). Never add a service that stores user or listing data outside KSA (no Vercel, no Supabase Cloud, no foreign S3 or CDN for data) without the owner's written approval.
2. **Every listing needs a REGA ad licence number.** The listing form starts from the licence number, and data is pulled from REGA. Never let users free-type fields that REGA supplies.
3. **Advertisers are verified through Nafath** before they can post. Buyers log in with a phone OTP only.
4. **Expired licences mean takedown.** A nightly job hides any listing whose REGA licence has expired. Admin has a one-click takedown with a reason.
5. **ZATCA e-invoice for every payment** (credit top-ups).
6. **Personal data** (PDPL): collect the minimum, never log national IDs, phone numbers or OTPs in plain text, and mask them in admin lists.

Until the real REGA, Nafath and ZATCA access is granted, each integration runs behind an adapter with a `mock` mode (see §6).

## 3. Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS, `next-intl` for Arabic/English, PWA |
| Backend | Django 5 + Django REST Framework, Python 3.12 |
| Database | PostgreSQL 16 + PostGIS (GeoDjango) |
| Jobs | Celery + Celery Beat, Redis |
| Files | S3-compatible storage (SeaweedFS locally, OCI Object Storage in production), imgproxy for resizing |
| Search | PostgreSQL full-text + PostGIS at launch; Typesense later (phase 2) |
| Maps | Mapbox GL or Google Maps JS (free tier), behind a small wrapper component |
| Auth | Phone OTP (buyers); Nafath (advertisers); JWT via `djangorestframework-simplejwt`, httpOnly cookies |
| Payments | Moyasar first (mada, Apple Pay, STC Pay), behind a `payments` adapter |
| Messaging | WhatsApp Cloud API (leads); Saudi SMS provider (Unifonic or Taqnyat) for OTP |
| Deploy | Docker Compose locally → Coolify on Oracle Cloud (KSA region) |
| Monitoring | Uptime Kuma, GlitchTip (Sentry-compatible) |

Don't add new frameworks or paid services without asking the owner first.

## 4. Repository layout

```
/
├── CLAUDE.md
├── docker-compose.yml          # local development stack
├── docker-compose.prod.yml     # production overrides (used by Coolify)
├── .env.example                # every env var, documented; real .env is git-ignored
├── Makefile                    # shortcuts: make up, make migrate, make test …
├── backend/                    # Django project
│   ├── config/                 # settings (base.py, local.py, production.py), urls, celery
│   ├── apps/
│   │   ├── accounts/           # users, roles, OTP, Nafath verification
│   │   ├── brokers/            # broker + agency profiles, FAL licence
│   │   ├── listings/           # listings, photos, REGA licence data, expiry
│   │   ├── locations/          # cities, districts (bilingual), geo data
│   │   ├── leads/              # enquiries, WhatsApp/call tracking
│   │   ├── wallet/             # credits ledger, pricing table, spend actions
│   │   ├── payments/           # top-ups, payment gateway adapter
│   │   ├── invoicing/          # ZATCA e-invoices
│   │   └── seo/                # area-page data, sitemaps
│   ├── integrations/           # rega/, nafath/, zatca/, sms/, whatsapp/ — each with mock + live clients
│   └── requirements/           # base.txt, local.txt, production.txt
└── frontend/                   # Next.js app
    ├── app/[locale]/           # ar (default) and en routes
    ├── components/
    ├── lib/api/                # typed API client
    └── messages/               # ar.json, en.json
```

## 5. Local development (Docker Desktop)

Services in `docker-compose.yml`:

| Service | Image / build | Port |
| --- | --- | --- |
| `db` | `postgis/postgis:16-3.4` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |
| `storage` | `chrislusf/seaweedfs` (S3 API) | 8333 |
| `imgproxy` | `darthsim/imgproxy` | 8081 |
| `api` | `./backend` (Django, runserver with reload) | 8000 |
| `worker` | `./backend` (celery worker) | — |
| `beat` | `./backend` (celery beat) | — |
| `web` | `./frontend` (next dev) | 3000 |
| `mailpit` | `axllent/mailpit` (catches emails) | 8025 |

Common commands (also in the Makefile):
```bash
docker compose up -d --build                         # start everything
docker compose logs -f api                           # follow backend logs
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
docker compose exec api python manage.py seed_demo   # cities, districts, demo brokers + listings
docker compose exec api pytest
docker compose exec web npm run lint && docker compose exec web npm run typecheck
docker compose down                                  # stop (add -v to wipe data)
```
- Site: http://localhost:3000 · API: http://localhost:8000/api/ · Admin: http://localhost:8000/admin/ · Files (S3): http://localhost:8333
- Local mode uses `INTEGRATIONS_MODE=mock`: OTP codes print to the `api` logs, Nafath auto-approves a test identity, REGA returns fake licence data, and payments use the gateway's test mode.
- Source code is mounted as volumes so edits reload live. Database data lives in a named volume.

## 6. Coding conventions

**General**
- Arabic is the default locale, and the UI must be fully RTL-correct. Use logical CSS properties (`ms-`, `me-`, `ps-`, `pe-` in Tailwind), never left/right.
- Bilingual content fields are stored as `name_ar` / `name_en` (likewise `title_`, `description_`).
- Store times in UTC and display them in `Asia/Riyadh`. Use Gregorian dates in the UI; Hijri is optional, for display only.
- **Money** is stored as integer **halalas** (1 SAR = 100). **Credits** are integers. Never use floats for either.
- Settings come from environment variables via `django-environ`. Never commit secrets.

**Git workflow**
- Every main feature (one item group from §7, e.g. listings or wallet) gets its own branch from `master`, named `feat/<short-name>`.
- Commit all the work for that feature to its branch.
- **Never merge into `master`, or push `master`, until the owner explicitly says so.** When a feature is done, report the branch name and wait.
- Fixes to a feature that is still waiting for review go on that same feature branch.

**Backend (Django)**
- One Django app per domain (§4). Business logic goes in `services.py`, not in views or serializers.
- **The wallet is an append-only ledger.** `CreditTransaction` rows are never edited or deleted. Balance = sum of the ledger, cached on `Wallet` and updated inside `transaction.atomic()` with `select_for_update()`.
- Credit prices live in a `CreditPrice` table editable in admin, never in code.
- Each external system has an adapter in `integrations/<name>/` with a shared interface, a `MockClient` and a `LiveClient`, selected by `INTEGRATIONS_MODE`. Views never call third-party APIs directly.
- Use Celery for anything slow or scheduled (REGA sync, expiry, image processing, notifications). Tasks must be idempotent.
- Every API endpoint has permission classes; default to deny.
- Tests use pytest + pytest-django + factory_boy. Every service function gets tests, and wallet and payment code needs near-full coverage.
- Lint and format with `ruff`.

**Frontend (Next.js)**
- TypeScript strict mode. Use Server Components by default; add `"use client"` only when needed.
- Listing, search and area pages are server-rendered for SEO, with `generateMetadata`, `hreflang` alternates and JSON-LD (`RealEstateListing`).
- All text goes through `next-intl`. No hard-coded strings in components.
- Use the API client in `lib/api/` only. Don't scatter `fetch` calls.
- Images are served through imgproxy URLs with explicit sizes.
- Mobile-first: most users browse on phones.

## 7. Phase 1 — MVP (build now, about 3 months)

Goal: a REGA-compliant portal that 10–20 Eastern Province launch brokers can use, with paid credits switched on once they see leads.

**Accounts and verification**
- [ ] Custom `User` model with phone as the login. Roles: `buyer`, `owner`, `broker`, `agency_admin`, `staff`.
- [ ] Phone OTP login (SMS adapter; rate-limited; codes hashed; 5-minute expiry).
- [ ] Nafath verification flow for anyone who posts (adapter + mock). Store only the verification status and reference, not the ID number.
- [ ] Broker profile: name (ar/en), photo, FAL licence number, agency link, WhatsApp number, cities served.
- [ ] Agency profile: logo, CR number, FAL licence, members.

**Listings**
- [ ] Create a listing by entering the REGA ad licence number → fetch licence data (adapter) → broker adds price, photos and description.
- [ ] Fields: purpose (sale/rent), rent period, property type, price, area m², bedrooms, bathrooms, furnishing, ready/off-plan, city, district, map point, amenities, licence number and expiry.
- [ ] Photo upload straight to S3 (presigned URLs), reorder, cover photo; resized via imgproxy.
- [ ] Statuses: `draft → pending_review → active → expired / taken_down / archived`.
- [ ] Listing page shows a REGA licence badge with the licence number.

**Search and browse**
- [ ] Buy/rent search with filters: city, district, type, price range, beds, baths, area, ready/off-plan.
- [ ] Sort by newest, price and featured; featured listings are pinned on top.
- [ ] Map view (PostGIS bounding-box query) alongside the list view.
- [ ] Favourites for logged-in users.

**Leads**
- [ ] WhatsApp button (deep link with a pre-filled message including the listing reference), call button and enquiry form.
- [ ] Every lead is logged (listing, broker, channel, time) and the broker is notified on WhatsApp.

**Credits wallet and payments**
- [ ] Wallet per broker or agency; ledger; balance shown in the dashboard.
- [ ] Spend actions: post (30 days), refresh (back to the top), feature (badge plus top slots for N days). Costs come from `CreditPrice`.
- [ ] Top-up packages paid with mada, Apple Pay or STC Pay via the Moyasar adapter, with webhook verification.
- [ ] ZATCA e-invoice issued for every successful top-up (adapter + mock), with a PDF download.
- [ ] Launch promotion: admin can grant free credits (ledger type `grant`). Owner listings are free.

**Broker dashboard (Next.js)**
- [ ] My listings (status, expiry, views, leads), post/edit, refresh/feature buttons, wallet and invoices, profile.

**SEO**
- [ ] Arabic and English area pages, e.g. `/ar/للإيجار/شقق/الدمام/الشعلة` and `/en/rent/apartments/dammam/al-shulah`, generated from city × district × type × purpose, with listing counts.
- [ ] `sitemap.xml` (split by type), `robots.txt`, canonical URLs, Open Graph images.

**Admin and operations (Django admin)**
- [ ] Moderation queue for pending listings; approve/reject with a reason.
- [ ] One-click takedown with a reason, which is logged.
- [ ] Wallet adjustments (ledger entries only), credit price table, cities and districts.
- [ ] REGA sync log and integration error log.
- [ ] Nightly Celery Beat job: expire listings whose licence or 30-day post period has ended; notify brokers 3 days before.

**Platform**
- [ ] Docker Compose for local development (§5); production compose file for Coolify (§10).
- [ ] Seed command with real Eastern Province cities and districts (ar/en) and demo data.
- [ ] Basic analytics: listing views and leads per listing (stored in our own database, no third-party trackers at launch).
- [ ] Terms, privacy policy and REGA licence pages (content provided by the owner).

**Phase 1 exit gate:** REGA platform licence granted, real REGA/Nafath/ZATCA clients live, 20 launch brokers onboarded.

## 8. Later phases (do NOT build until the owner says so)

Keep the data model ready for these, but don't implement them early.

**Phase 2 — Monetize (months 4–6). Gate: brokers renew credits every month.**
- Saved searches with email/WhatsApp alerts
- Broker lead inbox (statuses, notes) and listing performance stats
- Agency credit packages and sub-accounts sharing a wallet
- New Projects pages for developers, with lead forms
- Photography service booked with credits
- Top-broker ranking and badges
- Typesense search (when listings pass ~50,000 or search slows down)

**Phase 3 — Grow (months 7–12). Gate: a steady paid broker base.**
- iOS and Android apps (React Native / Expo, using the same API)
- AI search in Arabic ("3-bedroom villa near a school in Khobar under 1.5M")
- Price estimates and area price trends
- 360° tours and video
- Mortgage referrals to partner banks

**Phase 4 — Expand (year 2).**
- Broker CRM as its own SaaS product
- Daily/holiday rentals (needs a Ministry of Tourism licence)
- Data reports for developers
- Commercial property listings
- Riyadh and Jeddah expansion (data and SEO pages per city)

## 9. Definition of done (every task)

1. `docker compose exec api pytest` passes, and `ruff check` is clean.
2. `npm run lint` and `npm run typecheck` pass in `frontend`.
3. New migrations are created and applied; no migration is edited after it has been merged.
4. The UI works in Arabic (RTL) and English, on mobile width (390 px) and on desktop.
5. Any new env var is added to `.env.example` with a comment.
6. A short plain-language summary for the owner: what changed, how to try it, any follow-up, and the feature branch name. The branch is left unmerged until the owner approves (see Git workflow in §6).

## 10. Deployment — Oracle Cloud (later, after phase 1 is ready locally)

- **Region:** Oracle Cloud Jeddah or Riyadh. Nothing that holds data runs outside KSA.
- **Servers (start):** one VM for the app (4 OCPU/vCPU, 16 GB) running Coolify, and one VM or managed service for PostgreSQL + PostGIS, with daily backups to Object Storage.
- **Files:** OCI Object Storage through its S3-compatible API (same code as local SeaweedFS; only the env vars change).
- **Coolify** deploys from the Git repo using `docker-compose.prod.yml`: Gunicorn for Django, `next build && next start` for the frontend, Celery worker and beat, Redis and imgproxy. Coolify provides HTTPS (Let's Encrypt) and the domain.
- **Production settings:** `DEBUG=False`, strict `ALLOWED_HOSTS` and CORS, secure cookies, HSTS, `INTEGRATIONS_MODE=live`.
- **Order of steps:** staging subdomain first → test the full flow with real test payments → production.
- Ask the owner before any step that costs money or touches production data.

## 11. Open questions (check with the owner; don't guess)

- Brand name and domain
- REGA platform API specification and access credentials
- Nafath integration route (direct or through an approved provider)
- Final credit prices and top-up packages (set after the broker pilot)
- Choice of SMS provider and of the payment gateway contract
- Oracle region: Jeddah or Riyadh
