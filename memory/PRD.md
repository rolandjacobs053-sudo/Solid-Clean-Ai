# Solid Clean Ltd - Business platform (on CleanOps multi-tenant core)

## Original problem statement (latest, 2026-10-20 - "SOLID CLEAN LTD COMPLETE MASTER PROMPT", key wording)
"I own Solid Clean Ltd. I want to develop my existing Emergent application into a professional, secure, scalable and cost-effective business platform ... one central private management system while keeping my public website separate."
Non-negotiables (verbatim): "Modify my existing Emergent project. Do not create a new replacement project. Do not rebuild the entire application from scratch. Do not import my old WordPress website ... Preserve existing working features ... Do not delete data or perform destructive database changes without my approval ... Do not change my live domain, DNS, email routing, payment configuration, company details or live prices without permission. Do not purchase software, API credits, subscriptions ... without my explicit approval. Do not invent company information, prices, legal terms ... Audit the existing application before making changes. Implement changes in stages."
"NEVER ASK CUSTOMERS ABOUT PARKING." "Never include Airbnb cleaning or holiday-let cleaning anywhere."
Modules requested: public website + booking, policies & acknowledgments, central pricing, AI support, AI telephone receptionist (020 3728 4419 - do not port), CRM, commercial lead gen, sales pipeline (13 stages), commercial quotations & agreements, Contracts & Electronic Signatures (templates, wizard, approval workflow, multi-signatory, audit trail, signed PDF storage, renewals, onboarding/offboarding), staff ops (scheduling, checklists, QC, incidents), OWNER-ONLY Road Charge & Travel Cost Checker (Congestion Charge/ULEZ, profitability), payments/invoices/expenses, SEO, marketing, AI daily report, RBAC (Owner, Administrator, Manager, Supervisor, Cleaner, Contractor, Contract recipient, Customer), security, cost control.
Phases requested: 1 Audit → 2 Website & booking → 3 Private system/RBAC → 4 Contracts & e-sign → 5 Travel checker → 6 Commercial sales → 7 AI & marketing → 8 E2E testing.
Approved company details: Solid Clean Ltd, solidcleanltd.com, info@solidcleanltd.com, 020 3728 4419, London and Surrey.
Earlier history: started as an integrated Solid Clean system, then a multi-tenant SaaS ("CleanOps"), then refocused on Solid Clean first with the SaaS core kept in the background.

## Architecture
- FastAPI + MongoDB, multi-tenant via `company_id` + ContextVar (`core.TenantDB`). Public routes use `/api/public/{slug}`; admin routes use the JWT `company_id`
- Roles now: platform_admin, owner, staff (staff = own assigned bookings + policies)
- Stripe Checkout (TEST mode) for booking payments into one account; SaaS subscriptions exist in the background
- Email: `mailer.py` (Emergent-managed Resend) + `comms.log_comm` (sends transactional email; marketing is simulated; scheduled items are sent by `automations.run_automations`)
- Voice: `routes_voice.py` Twilio TwiML webhooks (`/api/voice/incoming`, `/api/voice/{slug}/{cid}/speech`), tenant chosen by `business.voice_number`; needs `TWILIO_AUTH_TOKEN`
- Audit report: `/app/memory/AUDIT_REPORT.md`

## Implemented
- 2026-10-11: SaaS core, Solid Clean public site + booking, CRM, AI chat, marketing tools, policies, Stripe, RBAC, Airbnb/parking removal
- 2026-10-20: removed Standard Cleaning; removed "Get a Quote" buttons (Book a Cleaning kept); new extras (Single/Double oven, Dishwasher, Blinds); Supplies & equipment £25; real transactional email (quotes, confirmations, day-before reminders); Staff schedule weekly calendar (/admin/schedule); AI phone receptionist code (NOT CONNECTED - awaiting Twilio); audit report

- 2026-10-20 (later): user request "Website looks very simple... customers upload photographs... retrieve my original policies... show me my private management dashboard". Delivered: call-focused site (call strip, header phone, hero call, call band, mobile Call/Book bar); 8-step booking (Service → Property [EoT adds furnished/flooring] → "Upload Photos of Your Property" → Extras → Access [estate agency keys] → Date & details → Terms → Review); photos in Emergent object storage (`routes_photos.py`, `storage.py`), private and linked to booking/lead, viewable in the admin BookingDetail sheet (Bookings, Staff schedule, Lead drawer); extras Freezer defrost £75 (replaces fridge clean) and Hob £25, Supplies £25 kept; 50% deposit (payment_mode deposit_50) plus "Email balance payment link"; the owner's Company Policy published verbatim (section 12 order fixed) plus the old-site FAQ guarantee/refund/breakage wording (with the old FAQ phone/email swapped for the approved ones); owner alerts go to info@solidcleanltd.com; login lockout now uses X-Forwarded-For; stale pending photos are soft-deleted after 24h. Old-site Terms/Privacy/Refund pages were WordPress theme placeholders, so nothing was imported from them. Service name kept as "Residential / Regular Clean" (user's instruction).
- Tests: iteration_4 backend 11/11, frontend flows pass; the PhotoUploader overlay/replace bugs were fixed afterwards

- 2026-10-20 (round 3): user chose FULL payment at booking ("front page of the website is full payment not 50% of deposit"). payment_mode full_upfront; KB updated; Company Policy draft has [REVIEW REQUIRED] markers on deposit sections 1, 2, 3, 6, 13. The PUBLISHED v1 still mentions the 50% deposit until the owner sends new wording (open issue). Added N, E, W, NW, EC, WC postcodes. Privacy policy DRAFT (covers photos/bookings) via scripts/privacy_draft_2026_10.py, unpublished. Before/after job photos (POST /api/admin/bookings/{id}/photos kind=before|after; staff only on assigned jobs). Commercial Cleaning page /commercial-cleaning (10 premises types, local images in /public/commercial, "BOOK A FREE SITE WALKTHROUGH"), tailored walkthrough form with photos and preferred/alternative visit times (request only), confirmation text verbatim; routes_walkthrough.py (public POST with a 3-per-email-per-day cap; owner-only admin list/detail/PATCH confirm/propose/visited/decline with customer emails); admin page /admin/walkthroughs. Tests: iteration_5 backend 22/22, frontend flows pass; minor follow-ups fixed afterwards (date validation, message reset, status lock, labels, card alignment, file input reset).

- 2026-10-20 (round 4): admin and login rebranded "Solid Clean Ltd" (logo, green/gold); installable app (manifest.json, icons in /public/icons, sw.js, Install app button + help dialog, mobile sign-out); a shared BookingShell layout for /quote and /commercial-cleaning/request; the address is now asked at the END of every form; Commercial page rebuilt (hero, How it works, 10 premises cards linking to the 6-step walkthrough request: Premises → Requirements → Photos → Site visit → Your details → Address); selecting "Commercial / Office Cleaning" on /quote now routes to the walkthrough request instead of the residential property step (bug fix). Tests: iteration_6 + iteration_7 frontend 100%.

- 2026-10-20 (round 5): user uploaded "TERMS AND CONDITIONS.pdf" ("Use this discard another this is terms policy company"). The old deposit-based Company Policy (terms v1) was replaced with the T&C published word for word as "Terms and Conditions" v2 (scripts/publish_terms_2026_10.py), and customers must accept it at checkout. FAQ "How do I pay?" / "Can I reschedule or cancel?" now use full-payment and tiered-refund wording (DB + seed.py), and seed payment_mode is now full_upfront. Checked: /terms and /policies show v2 with no deposit wording (desktop + mobile).

- 2026-10-20 (round 6): old "Service guarantee, refunds & breakages" policy unpublished (new owner-only Unpublish button; public config, booking terms and AI receptionist skip unpublished policies). Owner-only "Cancel & refund" on paid bookings: suggests 100% / 50% / 0% from the notice rules (plus any tip in full), owner can edit the amount, and it only RECORDS the refund (payment_status refund_due) and emails the customer; the owner refunds manually in Stripe. A required "I have read and accept the Terms and Conditions, including the cancellation and refund policy" checkbox sits next to Pay (backend 409 without it). Optional tip at checkout (Stripe line item). Owner "Send tip request" on completed bookings emails a link to the public /tip/{id}?t= page (Stripe payment, stored as after_tip, owner notified). Tested in iteration_8.
- 2026-10-20 (round 7): Carpet Cleaning is now a separate service. /carpet-cleaning page: new generated hero image (technician + commercial extraction machine), description from the old website, What's included, "Prices starting from £100" explained as a starting price, 8 area image cards, 5-step process. /carpet-cleaning/request: areas + counts, stairs questions (steps, landing, stairs photos), condition, pets and treatment questions, a no-guarantee disclaimer, multiple photos, preferred date/time (a request only), contact details, address last. It creates a carpet_quotes doc (awaiting_review), not a booking. Admin /admin/carpet-quotes: Send quote (price/date/time/message, emails the link /carpet-cleaning/quote/{id}?t=) → the customer accepts T&C and pays in full via Stripe → booking awaiting_approval → owner Approve → confirmed (confirmation + reminder). Decline after payment records a full refund. Stale or declined checkout sessions are expired, and any late payment is auto-flagged refund_due. Carpet is blocked from the instant /quote booking (redirected). Desktop "Call us" opens a dialog with the number + Copy; tel links use +44. Tested in iteration_9 (18/18 backend after the fix).
- 2026-10-20 (round 8): Per-item extras with quantity selector (blinds, windows, balcony, wall washing, skirting, mattress, sofa, rug, curtains) + new flat extras (conservatory, garage, garden furniture). All prices are PLACEHOLDERS for the owner to edit. Live "Your price so far" bar on the Extras step. New Settings Extras editor (name, price, per item, unit, max qty, add/remove; new extras are auto-added to services). Before & after: cleaners/owner upload job photos (and can delete them); owner "Send to customer" emails a private /results/{id}?t= link (public endpoints /api/public/{slug}/photos/results/...). Tested in iteration_10 (100%).
- 2026-10-20 (round 9): New Residential Cleaning form /residential-cleaning/book (separate from EoT; /quote "Residential" redirects there). Steps: frequency (one-off/weekly/fortnightly/monthly) → property (type, beds, baths, people, pets, last cleaned) → services (included tasks + paid beds/dishes/laundry/ironing + other request) + add-ons → date/time → contact → address + access → optional photos → review & pay. Pricing: size × (last cleaned × people × pets) + services/add-ons → min top-up → frequency discount (weekly 15 / fortnightly 10 / monthly 5 %, PLACEHOLDERS editable in Settings → Residential panel). Recurring: first clean paid now with the card saved (consent checkbox required); a daily cron (.emergent/crons.yml → POST /api/cron/recurring, WEBHOOK_CRON_SECRET) creates the next visit and charges the saved card off-session 2 days before; failures email the customer + owner. Admin booking detail: residential answers + Regular clean pause/resume/cancel; cancelling the first booking cancels the plan. Removed extras at the owner's request: garden furniture, wall washing, mattress, sofa, rug, curtains. Tested in iterations 11-12 (backend 41/41 targeted after fixes, frontend 100%).
- Pending: Google reviews (Places API (New)) - need the owner's GOOGLE_PLACES_API_KEY (playbook received). AI phone answering - owner said "later".
- 2026-10-20 (round 10): Admin "Regular clients" page (/admin/regular-clients, GET /api/admin/recurring, owner only): stats (active, paused, last payment failed, expected per month), tabs, next visit, last visit payment status, card saved, pause/resume/cancel. Real-review collector: completing a job emails a "Rate your clean" link to /feedback/{id}?t= (stars, comment, display name, publish consent). Consented reviews show on the public /reviews page as "Verified customer". The owner can hide one only with a reason (offensive/fake/off-topic). Invented reviews were declined (UK DMCC Act 2024). Tested in iteration_13 (13/13 backend, frontend 100%).
- Pending: Google reviews - waiting for the owner's Google Places API key (the owner chose to wait). AI phone answering - "later".

## Open questions
- Twilio AI phone receptionist: waiting for the owner's Twilio Account SID, Auth Token and Twilio phone number (routes_voice.py exists; integration playbook received)
- "Service guarantee, refunds & breakages" (published v1) says "does not offer refunds", which conflicts with the T&C tiered refunds. Owner decision needed: unpublish or reword
- T&C says "Solid Clean" (not Ltd) and allows bank transfer, but online booking takes card payments through Stripe only
- Freezer defrost "includes fridge/freezer cleaning" wording needs owner confirmation
- Privacy policy still unpublished (draft); late-payment fee clause may need legal review

## Mocked / not connected
- SMS/WhatsApp SIMULATED; cold email SIMULATED; phone receptionist NOT CONNECTED; Google APIs not connected; Stripe TEST mode
- Owner alert email is a placeholder; provisional prices: Double oven £65, Dishwasher £20, Blinds £20

## Roadmap (awaiting owner approval of plan)
- P0 Phase 2: publish approved policies (drafts need review), parking policy wording, SEO basics (title/meta/sitemap/robots/schema), Solid Clean branding in admin, CORS lock-down, scheduled jobs via platform crons
- P0 Phase 3: extended roles (Administrator, Manager, Supervisor, Cleaner, Contractor), per-permission server checks
- P1 Phase 4: Contracts & Electronic Signatures (built-in signing recommended) + object storage
- P1 Phase 5: owner-only Road Charge & Travel Cost Checker + job profitability + expenses
- P1 Phase 6: commercial pipeline (13 stages), commercial quotes & agreements
- P2 Phase 7: Twilio voice connect, SMS, daily AI report, Google integrations

## 2026-10-20 - Google visibility (SEO)
- User: "I can't see website on Google". Live domain: solidcleanltd.com.
- Added public/robots.txt (blocks admin/login/private links), public/sitemap.xml (19 public pages), LocalBusiness JSON-LD, OG/Twitter tags, canonical, crawler-readable noscript text in index.html.
- SeoManager (components/site/SeoManager.jsx) sets per-page title/description/canonical; non-public routes get noindex.
- Pending on user: verify domain in Google Search Console, submit sitemap, create Google Business Profile; opening hours/address not provided (left out of structured data).

## 2026-10-20 - Opening hours for Google listing
- Admin Settings > Business: structured Opening hours editor (per day open/closed + times), saved as business.opening_hours.
- Public config exposes opening_hours; Contact page shows formatted hours; LocalBusiness JSON-LD gets openingHoursSpecification.
- Address intentionally not published (service-area business). Real hours not yet entered by owner.


## 2026-10-20 - SEO production domain
- User confirmed production domain: https://solid-clean-ai.emergent.host. Switched canonical, og:url, JSON-LD, sitemap.xml (19 URLs) and robots.txt Sitemap line to it (SeoManager SITE constant).
- Verified on preview: all 19 sitemap pages 200, index/follow, unique titles, correct canonicals; robots.txt and sitemap.xml valid. Live production site had no X-Robots-Tag/noindex. Needs re-publish to push domain change live.
- If a custom domain (solidcleanltd.com) is connected later, update SITE in SeoManager.jsx, index.html, sitemap.xml and robots.txt.


## 2026-10-21 - AI Business Manager (owner only)
- User master prompt: "SOLID CLEAN AI — BUSINESS MANAGEMENT AND GROWTH ASSISTANT" (text + voice AI business partner, priorities, memory, finance, strict approval rules, no invented figures).
- Choices: Claude Sonnet 5.5 (Universal Key); OpenAI Whisper STT + OpenAI TTS tts-1 voice "sage" (Universal Key, usage-billed); Expenses page + per-job costs; owner only (default); preview only, not published.
- Backend: business_data.py (snapshot + month_metrics, excludes demo, London date), routes_manager.py (/api/admin/manager: chats CRUD/search, SSE messages w/ stop + saved partials, REMEMBER suggestions persisted, transcribe, speak, memory CRUD w/ dedupe, priorities generate/patch/plan, snapshot), routes_finance.py (/api/admin/finance: summary+trend, expenses CRUD, jobs, per-job costs). All require_owner.
- Frontend: /admin/business-manager (Assistant / My Business Priorities / Business memory tabs), hooks useVoice (MediaRecorder + silence auto-stop, hands-free, iOS audio unlock) & useManagerChat (fetch SSE + AbortController), components/manager/*, /admin/finance page. Nav items owner-only.
- Tested: iteration_14 (27 backend tests pass, full UI incl. voice loop with injected speech, mobile). Follow-up fixes: demo filter on escalations/carpet/walkthroughs, quotes split into contactable vs anonymous price checks, mobile tabs scroll, voice "thinking" state, chat delete error handling.
- Known: Overview dashboard counts demo records while Manager/Finance exclude them. No Google Business Profile / Search Console / Ads / accounting data connected.

## 2026-10-21 - Growth partner (£400m ambition) + Customer Management
- User asks: AI Business Manager built around scaling to £400m revenue or valuation; wide knowledge sources (web, YouTube, books, social, podcasts) organised into a searchable knowledge base; roadmap, goals, analysis, alerts, reports (dashboard only; owner email gilmar@solidcleanltd.com noted for future), approval queue. Plus Customer Management (manual profiles, dashboard bookings, edit/reschedule/cancel, conflicts, search, UK GDPR).
- Backend: routes_customers.py (/api/admin/customers: CRUD, search, duplicate 409, manual bookings w/ conflict check (hard double booking vs capacity override), edit/reschedule, owner-only GDPR erase), routes_knowledge.py (/api/admin/knowledge: URL/YouTube/pasted-text ingest -> AI lesson extraction with evidence levels, dedupe, outdated flag, SSRF guard; relevant() retrieval; seed from knowledge_seed.json at startup for comped/active tenants), routes_strategy.py (/api/admin/strategy: goals w/ live progress, insights, async roadmap + reports via jobs collection + polling, approvals scan/edit/approve(send via log_comm)/reject; /api/cron/manager-report/{daily|weekly}), business_data.deep_metrics + insights. Manager chat context now includes roadmap, goals, alerts, approvals, relevant knowledge.
- Crons: manager-daily-brief 06:30 and manager-weekly-review Mon 07:00 Europe/London (alongside recurring-cleans).
- Frontend: /admin/customers, /admin/customers/:id; Business Manager tabs Goals & Roadmap, Reports, Approvals, Industry knowledge; Alerts strip in Assistant.
- Knowledge base: 107 lessons from 18 sources actually read (case studies: ISS, Mitie, ABM, Rentokil Initial, ServiceMaster, Merry Maids, Jani-King, Molly Maid, Tidy Casa, Queen Bee; valuation benchmarks; commercial bidding guides; BCC research news; franchising).
- Limitations: YouTube transcript fetch blocked from server (RequestBlocked) -> paste transcript; TikTok/Instagram/Facebook/LinkedIn/X refused (login walls) -> paste captions; paywalled/blocked sites need pasted text; no live web search (needs paid API e.g. Perplexity, owner approval).
- Tested: iteration_15 (20/20 backend + full UI) and iteration_16 (fix retest 11/11). Post-test fixes: SSRF redirect re-check, atomic job lock (unique index jobs company_id+kind), polling timeout message, customer upcoming stat uses ACTIVE.




## 2026-10-21 - Live web research (Perplexity) - code ready, KEY PENDING
- research.py: Perplexity Agent API (POST /v1/agent preset "fast", fallback /v1/sonar), parses output_text/output/choices + search_results/citations; weekly cap 20 searches (research_log). Key env: PERPLEXITY_API_KEY (not set yet -> UI shows "not connected", endpoints return 409).
- /api/admin/knowledge/research/status, POST /api/admin/knowledge/research (async job "research" -> lessons with citations, source_type web_research). Chat MessageIn.web=true runs a live search and injects cited results.
- Cron manager-weekly-research Mon 05:00 London -> /api/cron/manager-report/research (4 rotating topics, skipped without key).
- UI: "Search the web" switch in composer (disabled until connected), Live web research panel in Industry knowledge tab.
- First publish requested 2026-10-21 (before research code); needs re-publish after key is added.


## 2026-10-21 - Claude model picker + TTS settings
- Business Manager per-conversation model: Claude Opus 5.5 (claude-opus-5-5), Sonnet 5.5 (default, claude-sonnet-5-5), Haiku 4.5 (claude-haiku-4-5-20251001). Stored on manager_chats.model; GET /api/admin/manager/models; PATCH /chats/{id} {model}. Rest of app stays on Sonnet 5.5 (core.LLM_MODEL).
- TTS prefs (manager_prefs): default tts-1-hd, voice sage, speed 1.0; GET/PUT /api/admin/manager/prefs; /speak uses prefs (optional voice override). UI: model select + "Voice" popover (quality, voice, speed, preview); "Listen" on reports (chunked ~3500 chars, stop).
- Verified via curl (Haiku + Opus chats stream, HD speak 200) and mobile screenshot. Not yet published. Perplexity key still not provided.


## 2026-10-21 - Free web research (no key needed) + publish
- Owner chose a free option instead of a Perplexity key. research.py: if PERPLEXITY_API_KEY unset -> free mode: DuckDuckGo search (ddgs pkg, region uk-en, 8 results) + reads top 4 pages via routes_knowledge.fetch_source (SSRF-guarded) + Claude Sonnet 5.5 writes a cited [n] briefing. Perplexity is used automatically if a key is added later.
- connected() now always True; status.provider = "Free web search" | "Perplexity". Same 20/week cap. Weekly Monday research cron now active.
- Verified via curl: chat web=true returned cited London EoT prices; "Research now" job added 6 lessons from 8 sources (test data then deleted). Screenshot desktop+mobile: switch enabled "Search the web (20 left this week)".
- Re-publish dispatched 2026-10-21 (model picker, HD voice, Listen button, free web research).

## Backlog
- P0 Contract generation & e-signatures. P1 Congestion/ULEZ/travel cost calculator. P2 Google Reviews (needs Places key), Twilio phone receptionist (needs credentials). Optional: Perplexity key for deeper research.

