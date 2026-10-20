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

## Open questions
- Service-area postcode prefixes only cover South/South-West London + Surrey (SW, SE, CR, SM, KT, TW, BR, RH, GU). N, E, W, NW, EC, WC go to manual review. Owner to confirm
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
