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

## Open questions
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
