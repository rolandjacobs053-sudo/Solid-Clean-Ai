# CleanOps - AI SaaS for cleaning companies

## Original problem statement (latest, verbatim)
"I want to build an AI-powered SaaS platform for cleaning companies that I can sell to businesses worldwide through monthly subscriptions. The platform should include SEO tools, Google Ads management, cold email marketing, an AI receptionist that answers calls and customer questions, automated quotations and bookings, CRM, customer management, employee management and business analytics—all in one place. The platform must support multiple cleaning companies, with each company having its own account, data, settings and employees. I want to use Stripe to manage subscriptions. Companies should be able to choose a pricing plan, pay monthly or annually, upgrade or downgrade their plans, and cancel their subscriptions. Payments should be collected automatically, with failed-payment notifications and appropriate access restrictions for unpaid accounts. I also need an administrator dashboard to manage companies, subscription plans, payments and the overall platform. Please provide a quotation for developing an MVP and the complete platform, including the development cost, timeline, hosting, third-party software costs and ongoing maintenance. My goal is to build a scalable software business that generates recurring monthly revenue from cleaning companies, rather than developing software exclusively for my own company."
Follow-ups: "This should not be a cleaning website" / "It's not stripe subscription plan. I want to be able to accept payment via stripe" / "I don't want a cleaning company website or a landing page. I want a fully functional, AI-powered SaaS web application ... focus on building the actual software application, including its dashboard, functionality, integrations and subscription system ... support multiple cleaning businesses ... scale and add more features."
(Earlier brief: Solid Clean Ltd integrated AI cleaning business system — now the demo tenant.)

## Choices
- Build the SaaS MVP now, with the quotation as a page; self-serve sign-up with a 14-day trial (Growth); editable placeholder plans Starter £49 / Growth £99 / Pro £199 (annual = 10x monthly)
- Claude Sonnet 5.5 via Emergent LLM key; JWT cookie auth; Stripe claimable sandbox (test mode)
- Platform name "CleanOps" is a placeholder

## Architecture
- FastAPI + MongoDB. Multi-tenant through `company_id` on every document; `core.TenantDB` scopes all queries using a ContextVar set by the auth or slug dependency
- Roles: platform_admin, owner, staff. Access: `access_state()` checks trialing (until trial end), active, past_due (7-day grace), suspended, comped
- Plan features gate backend and nav: quotes_bookings, crm, analytics, ai_receptionist, reviews, outreach, marketing
- Stripe: plans synced to Products/Prices (lookup keys `{plan}_monthly|annual`), Checkout (subscription), in-app plan switch with proration, cancel/resume at period end, Billing Portal, invoices; webhook `/api/stripe/webhook` with a `/api/billing/sync` fallback
- Customer booking payments: Stripe Checkout through the platform account (tax-inclusive prices). Company setting `online_payments`; when it's off, the booking is confirmed and payment instructions are shown
- Routes: `/login`, `/signup`, `/admin/*` (company workspace), `/platform/*` (platform admin), `/c/:slug/quote` (each company's public booking widget, plus AI chat)

## Implemented (2026-10-11)
- Company workspace: overview analytics (revenue, CPL, CAC, conversion, channel profit), CRM leads + drawer, bookings (complete/cancel/assign staff), AI receptionist conversations, SEO audit + AI keyword/landing-page plan + AI Google Ads builder, cold email (AI drafts, reply classification, suppression list), reviews (AI reply drafts), marketing spend, communications log, team/staff, settings (pricing, availability, KB, business), billing
- Platform admin: MRR/ARR overview, companies (extend trial, suspend/reactivate), plan editor (synced to Stripe), payments, quotation, Solid Clean proposal
- Verified: tests 34/34 backend and 11/11 UI; subscribe → switch plan → cancel/resume → portal → past-due lock-out checked against the Stripe test API

## Mocked / not connected
- Email/SMS/WhatsApp sending SIMULATED (logged only); cold email sending SIMULATED; email verification is format-only
- Phone AI receptionist, Google Ads/GSC/GA4/GBP APIs: not connected
- Booking payments go to the platform Stripe account (Stripe Connect not built yet)

## Backlog
- P0: Stripe Connect so each company gets paid directly; real email provider (Resend) for transactional and billing emails
- P1: Voice AI receptionist (Vapi/Retell + Twilio); Google OAuth integrations; multi-currency/time zones; password reset
- P2: cleaner mobile app/rotas; WhatsApp; audit logs; data retention tools

## Next tasks
- Claim the Stripe sandbox; replace placeholder plan prices; connect an email provider
