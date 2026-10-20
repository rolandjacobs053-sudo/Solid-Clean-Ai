# Solid Clean Ltd - Audit of the existing Emergent project (2026-10-20)

Scope: the current preview app (FastAPI + MongoDB + React). The live domain solidcleanltd.com, DNS, email routing and Stripe live settings have NOT been touched.

## 1. What works (checked in this session or by earlier test runs)
| Area | Status | Evidence |
|---|---|---|
| Public website (Home, Services, Service areas, Reviews, FAQ, About, Contact, Policies, Booking) | Works | Earlier UI tests passed; screenshot today |
| Booking flow: service → property → rooms & extras → date/slot → details → Stripe Checkout | Works (Stripe TEST mode) | Earlier tests; availability is checked server-side; slot held while paying, then released if abandoned |
| Central pricing (services, per-room, extras, surcharges, promos, price history) | Works | One source of truth in `settings.pricing`; price history recorded |
| Services shown | Regular, End of Tenancy, Carpet, Commercial/Office (survey) | "Standard Cleaning" removed today |
| Extras | Single oven £45, Double oven £65*, Fridge/freezer £25, Dishwasher £20*, Blinds £20*, Interior windows £30, Cabinets £25, Balcony £25, Supplies & equipment £25 | *Provisional prices, need your approval |
| Parking | Removed from forms, pricing and DB; the AI is told never to ask | grep check today |
| Policy acceptance at booking | Recorded per booking with policy versions | `accepted_policies` on the booking |
| Auth | JWT httpOnly cookies, bcrypt, login lock-out after failed attempts | Earlier tests |
| Roles | owner, staff, platform_admin; enforced server-side | `require_admin`, `require_owner`; staff only reach Bookings (their own jobs) + Policies |
| CRM leads + timeline, quotes, bookings, staff assignment | Works | Earlier tests |
| AI web-chat receptionist (Claude via Emergent key) | Works | Uses price list, knowledge base and published policies; escalates complaints |
| Stripe webhook | Signature-verified; payment status checked with Stripe | `routes_public.py` |
| Transactional email (quotes, booking confirmations, reminders) | CONNECTED today (Emergent-managed Resend) | Test send returned "sent" |
| Staff schedule (weekly calendar, filter by cleaner; cleaners see only their own jobs) | NEW today | Screenshot desktop + mobile |

## 2. Incomplete / not connected
- Email: owner alert address is still a placeholder, so owner alerts are logged but not sent.
- SMS / WhatsApp: SIMULATED (logged only). No provider connected.
- Cold email outreach: SIMULATED (drafts only, never sent). Correct for now (PECR).
- AI telephone receptionist: code is built (Twilio voice webhooks, British voice, same brain as chat), but NOT CONNECTED. It needs a Twilio account and number. 020 3728 4419 has not been changed or ported.
- Google Ads / Search Console / GA4 / Google Business Profile: not connected (AI planning tools only).
- Reviews, prospects, marketing spend and 5 of 9 bookings / 9 of 13 leads are DEMO data (flagged `demo`, removable from Overview).
- Payments: Stripe is in TEST mode on the platform account. No live keys.

## 3. Broken or risky (needs fixing)
1. NONE of the 13 customer policies are published (`published_version = 0`), so customers can't read approved wording before booking. The drafts need your review and approval.
2. There's no Parking policy document, so the AI has nothing approved to say if a customer asks.
3. The browser tab title is "Emergent | Fullstack App". No meta description, sitemap.xml, robots.txt or structured data.
4. CORS is `*` with credentials. It should be limited to your real domains before going live.
5. The admin area is branded "CleanOps" (SaaS placeholder), not Solid Clean.
6. Reminders/follow-ups run in an in-process 30-minute loop. They should move to platform-managed scheduled jobs so they keep running reliably in production.

## 4. Missing entirely (from your master prompt)
- Roles: Administrator, Manager, Supervisor, Cleaner vs Contractor, Contract recipient, Customer accounts.
- Contracts & Electronic Signatures module (templates, wizard, approvals, signing, audit trail, signed PDFs, renewals).
- Secure document storage (needs object storage).
- Staff onboarding/offboarding, right-to-work tracking, checklists, quality checks, incident reports.
- Invoices module, expenses, job profitability.
- Owner-only Road Charge & Travel Cost Checker (Congestion Charge / ULEZ).
- Commercial sales pipeline with your 13 stages, commercial quotations and service agreements.
- Daily AI business report ("top 3 actions").

## 5. Public / private separation (current state)
- Public: `/`, `/services/*`, `/areas`, `/reviews`, `/faq`, `/about`, `/contact`, `/policies`, `/quote`. These are served by `/api/public/{slug}/*`, which only returns prices, availability, published policies and approved business details.
- Private: `/admin/*` (company) and `/platform/*` (SaaS owner). All `/api/admin/*` endpoints need a valid login and a role check on the server. Hidden buttons are not relied on.
- Recommendation: keep the single app and domain with the separation enforced on the server. A second domain or subdomain (e.g. manage.solidcleanltd.com) is optional and needs your approval.

## 6. Changes that could affect existing data
- Adding new roles: existing "staff" users would map to "Cleaner". This is additive, with no deletions.
- Removing demo data: only on your instruction (there's a button for it).
- Contracts/documents: new collections only.

## 7. External services: needed vs optional (no paid service will be activated without approval)
| Need | Option | Cost type |
|---|---|---|
| Email | Emergent-managed Resend (connected) | Uses Emergent credits |
| Phone AI | Twilio number + calls | Monthly number + per-minute (Twilio pricing) |
| SMS | Twilio SMS | Per message |
| E-signatures | A) Built-in signing (typed/drawn signature, consent, IP/time, SHA-256 hash, audit certificate) | No per-signature fee |
| | B) External provider (e.g. Dropbox Sign, DocuSign, Yousign, BoldSign) | Subscription / per envelope. Prices to be verified before approval |
| Document storage | Emergent object storage | Included / usage |
| Postcode → coordinates | postcodes.io | Free, open data |
| Zone boundaries | TfL / London Datastore open data + owner confirmation | Free |
| ULEZ vehicle compliance | No free official API. Use a manual check with a link to the TfL checker | Free (manual) |
| Routes / distance / fuel | Google Routes API (paid beyond free tier) or manual entry | To approve |
