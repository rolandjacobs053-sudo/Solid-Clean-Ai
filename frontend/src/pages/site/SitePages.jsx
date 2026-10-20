import { useEffect, useState } from "react";
import { Link, Navigate, useOutletContext, useParams } from "react-router-dom";
import { BadgeCheck, CalendarCheck, Camera, CreditCard, MapPin, Phone, ShieldCheck, Star } from "lucide-react";
import { toast } from "sonner";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";
import { hoursText } from "@/lib/hours";
import { BookBtn, CallBtn, G, GOLD, tel } from "@/pages/site/SiteLayout";

const IMG = {
  standard: "https://images.unsplash.com/photo-1639173925921-5d5fd027713c?crop=entropy&cs=srgb&fm=jpg&q=80&w=1000",
  regular: "https://images.unsplash.com/photo-1639173925921-5d5fd027713c?crop=entropy&cs=srgb&fm=jpg&q=80&w=1000",
  end_of_tenancy: "https://images.unsplash.com/photo-1564078516393-cf04bd966897?crop=entropy&cs=srgb&fm=jpg&q=80&w=1000",
  carpet: "/carpet/hero.jpg",
  commercial: "https://images.unsplash.com/photo-1662261896193-b4f8a02a9773?crop=entropy&cs=srgb&fm=jpg&q=80&w=1000",
};
const FALLBACK = { standard: "Routine cleaning to keep your home fresh and tidy.", regular: "A fresh, clean home without the hassle - every corner taken care of.", commercial: "Hygienic, welcoming offices and workspaces.",
  end_of_tenancy: "Thorough move-out cleaning for tenants, landlords and letting agents.", carpet: "Professional carpet cleaning for homes and workplaces." };
const services = (cfg) => cfg.pricing.services.filter((s) => s.active !== false);
const desc = (s) => s.description || FALLBACK[s.key] || "";

const Shell = ({ eyebrow, title, children, testid }) => (
  <main className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8" data-testid={testid}>
    <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: GOLD }}>{eyebrow}</p>
    <h1 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl" style={{ color: G }}>{title}</h1>
    <div className="mt-8">{children}</div>
  </main>
);

function ServiceGrid({ cfg }) {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {services(cfg).map((s) => (
        <Link key={s.key} to={s.key === "carpet" ? "/carpet-cleaning" : `/services/${s.key}`} className="group overflow-hidden rounded-3xl border border-slate-200 bg-white transition-transform hover:-translate-y-1" data-testid={`site-service-${s.key}`}>
          <img src={IMG[s.key] || IMG.regular} alt={s.name} className="h-44 w-full object-cover" />
          <div className="p-6">
            <h3 className="font-display text-lg font-semibold" style={{ color: G }}>{s.name}</h3>
            <p className="mt-2 text-sm text-slate-600">{desc(s)}</p>
            <p className="mt-3 font-mono text-sm" style={{ color: GOLD }}>{s.from_price ? `Prices from ${gbp(s.from_price)}` : s.requires_survey ? "Quote after survey" : `From ${gbp(s.pricing_mode === "per_room" ? s.min_price : s.fixed_price)}`}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}

export function HomePage() {
  const cfg = useOutletContext();
  const b = cfg.business;
  return (
    <main data-testid="site-home">
      <section className="relative overflow-hidden" style={{ background: "#f7f4fb" }}>
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:px-8 lg:py-24">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] rise" style={{ color: GOLD }}>Professional cleaning{b.service_areas_text ? ` · ${b.service_areas_text}` : ""}</p>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl rise rise-1" style={{ color: G }}>A spotless space,<br />booked in minutes.</h1>
            <p className="mt-6 max-w-lg text-base text-slate-600 sm:text-lg rise rise-2">See your exact price online, upload photos of your property and choose a genuinely available appointment - or simply call us and we'll help you choose the right clean.</p>
            <div className="mt-9 flex flex-wrap gap-3 rise rise-3"><BookBtn testid="hero-book-btn" />{b.phone && <CallBtn phone={b.phone} testid="hero-call-btn" />}</div>
            <div className="mt-10 flex flex-wrap gap-6 text-sm text-slate-700">
              {[[ShieldCheck, "Fully insured"], [BadgeCheck, "Uniformed, professional team"], [CreditCard, "Secure Stripe card payment"]].map(([I, t]) => <span key={t} className="flex items-center gap-2"><I className="h-4 w-4" style={{ color: GOLD }} />{t}</span>)}
            </div>
          </div>
          <img src={IMG.end_of_tenancy} alt="Freshly cleaned room" className="aspect-[4/3] w-full rounded-[2rem] object-cover shadow-2xl" />
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold sm:text-3xl" style={{ color: G }}>Our cleaning services</h2>
        <div className="mt-10"><ServiceGrid cfg={cfg} /></div>
      </section>
      {b.phone && (
        <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8" data-testid="home-call-band">
          <div className="grid items-center gap-8 rounded-[2rem] border-2 p-8 sm:p-12 lg:grid-cols-[1.4fr_1fr]" style={{ borderColor: GOLD, background: "#fbf9f1" }}>
            <div>
              <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: GOLD }}>Talk to a real person</p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl" style={{ color: G }}>Not sure which clean you need? Give us a call.</h2>
              <p className="mt-4 max-w-xl text-slate-600">Our team will talk you through the options, answer your questions and book your clean for you.</p>
            </div>
            <div className="flex flex-col gap-3">
              <a href={tel(b.phone)} className="flex items-center justify-center gap-3 rounded-full py-4 text-xl font-bold text-white transition-transform hover:-translate-y-0.5 sm:text-2xl" style={{ background: G }} data-testid="home-call-band-btn"><Phone className="h-6 w-6" style={{ color: "#d9c56a" }} /><span className="font-mono">{b.phone}</span></a>
              <BookBtn testid="home-call-band-book-btn">Or book online in minutes</BookBtn>
            </div>
          </div>
        </section>
      )}
      <section className="py-16 text-white" style={{ background: G }}>
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 md:grid-cols-4 lg:px-8">
          {[[Camera, "Tell us about the property", "Add details and photos"], [CalendarCheck, "Pick a time", "Only available slots are shown"], [CreditCard, "Pay securely", b.payment_mode === "deposit_50" ? "A 50% deposit confirms your booking" : "Full payment confirms your booking"], [BadgeCheck, "Relax", "Confirmation and reminder sent"]].map(([I, t, d], i) => (
            <div key={t} className="border-l border-white/20 pl-5"><span className="font-mono text-xs text-white/50">0{i + 1}</span><I className="mt-3 h-6 w-6" style={{ color: "#d9c56a" }} /><h3 className="mt-3 font-display text-lg font-semibold">{t}</h3><p className="text-sm text-white/70">{d}</p></div>
          ))}
        </div>
      </section>
    </main>
  );
}

export function ServicesPage() {
  const cfg = useOutletContext();
  return <Shell eyebrow="Services" title="Cleaning services" testid="site-services"><ServiceGrid cfg={cfg} /></Shell>;
}

export function ServiceDetail() {
  const cfg = useOutletContext();
  const { key } = useParams();
  const s = services(cfg).find((x) => x.key === key);
  if (!s) return <Navigate to="/services" replace />;
  const block = (t, v) => v && <div><h3 className="font-display font-semibold" style={{ color: G }}>{t}</h3><p className="mt-1 whitespace-pre-wrap text-slate-600">{v}</p></div>;
  return (
    <Shell eyebrow="Service" title={s.name} testid={`site-service-page-${s.key}`}>
      <div className="grid gap-10 lg:grid-cols-2">
        <div className="space-y-6">
          <p className="text-lg text-slate-700">{desc(s)}</p>
          {block("What's included", s.scope_included)}{block("Not included", s.scope_excluded)}{block("Before we arrive", s.preparation)}
          <div className="flex flex-wrap gap-3"><BookBtn testid="service-book-btn" /></div>
        </div>
        <img src={IMG[s.key] || IMG.regular} alt={s.name} className="aspect-[4/3] w-full rounded-3xl object-cover" />
      </div>
    </Shell>
  );
}

export function FaqPage() {
  const cfg = useOutletContext();
  return (
    <Shell eyebrow="FAQ" title="Frequently asked questions" testid="site-faq">
      <Accordion type="single" collapsible className="max-w-3xl">
        {cfg.knowledge_base.map((f, i) => <AccordionItem key={i} value={`f${i}`}><AccordionTrigger className="text-left" data-testid={`site-faq-${i}`}>{f.q}</AccordionTrigger><AccordionContent className="text-slate-600">{f.a}</AccordionContent></AccordionItem>)}
      </Accordion>
    </Shell>
  );
}

export function AreasPage() {
  const cfg = useOutletContext();
  const pre = cfg.pricing.service_area_prefixes;
  return (
    <Shell eyebrow="Coverage" title="Service areas" testid="site-areas">
      <p className="max-w-2xl text-slate-600">{cfg.business.service_areas_text ? `We cover ${cfg.business.service_areas_text}.` : "Enter your postcode when booking to check coverage."}</p>
      {pre.length > 0 && <div className="mt-6 flex flex-wrap gap-2">{pre.map((p) => <span key={p} className="flex items-center gap-1 rounded-full border px-4 py-2 font-mono text-sm" style={{ borderColor: GOLD, color: G }}><MapPin className="h-3.5 w-3.5" />{p}</span>)}</div>}
      <div className="mt-8"><BookBtn children="Check your postcode & book" testid="areas-book-btn" /></div>
    </Shell>
  );
}

export function ReviewsPage() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get(`/public/${DEFAULT_SLUG}/reviews`).then((r) => setRows(r.data)); }, []);
  return (
    <Shell eyebrow="Reviews" title="What customers say" testid="site-reviews">
      {rows?.length === 0 && <p className="text-slate-600" data-testid="site-reviews-empty">Verified customer reviews will appear here as they are received.</p>}
      <div className="grid gap-4 md:grid-cols-2">{rows?.map((r, i) => (
        <div key={i} className="rounded-2xl border bg-white p-6" data-testid="site-review-card">
          <div className="flex items-center justify-between"><span className="flex">{[1, 2, 3, 4, 5].map((n) => <Star key={n} className={`h-4 w-4 ${n <= r.rating ? "fill-amber-400 text-amber-400" : "text-slate-200"}`} />)}</span><span className="font-mono text-xs text-slate-400">{fmtDate(r.review_date)}</span></div>
          <p className="mt-3 text-slate-700">{r.text}</p><p className="mt-2 text-sm font-semibold" style={{ color: G }}>{r.author}{r.verified && <span className="ml-2 font-mono text-[10px] font-normal uppercase tracking-wider text-[#8F7E22]" data-testid="site-review-verified">Verified customer{r.service ? ` · ${r.service}` : ""}</span>}</p>
          {r.response && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600"><b>Our reply:</b> {r.response}</p>}
        </div>
      ))}</div>
    </Shell>
  );
}

export function AboutPage() {
  const cfg = useOutletContext();
  const b = cfg.business;
  return (
    <Shell eyebrow="About us" title={`About ${b.name}`} testid="site-about">
      <p className="max-w-3xl whitespace-pre-wrap text-lg leading-relaxed text-slate-700">{b.about_text || `${b.name} provides ${services(cfg).map((s) => s.name).join(", ")}. Every booking is confirmed with a reference and a reminder before your appointment.`}</p>
      <div className="mt-8 flex gap-3"><BookBtn /></div>
    </Shell>
  );
}

export function ContactPage() {
  const cfg = useOutletContext();
  const b = cfg.business;
  const [f, setF] = useState({ name: "", email: "", phone: "", message: "", marketing_consent: false });
  const [sent, setSent] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post(`/public/${DEFAULT_SLUG}/contact`, f); setSent(true); } catch (err) { toast.error(errMsg(err)); }
  };
  const real = (v) => v && !v.startsWith("[");
  return (
    <Shell eyebrow="Contact" title="Get in touch" testid="site-contact">
      <div className="grid gap-10 lg:grid-cols-2">
        <div className="space-y-3 text-slate-700">
          {real(b.phone) && <p>Phone: <a href={`tel:${b.phone.replace(/\s/g, "")}`} className="font-mono font-semibold" style={{ color: G }} data-testid="contact-phone">{b.phone}</a></p>}
          {real(b.contact_email) && <p>Email: <a href={`mailto:${b.contact_email}`} className="font-semibold" style={{ color: G }}>{b.contact_email}</a></p>}
          {(hoursText(b.opening_hours) || real(b.business_hours)) && <p data-testid="contact-hours">Hours: {hoursText(b.opening_hours) || b.business_hours}</p>}
          <div className="pt-4"><BookBtn /></div>
        </div>
        {sent ? <p className="rounded-2xl bg-green-50 p-6 text-green-900" data-testid="contact-success">Thank you - we've received your message and will get back to you shortly.</p> : (
          <form onSubmit={submit} className="space-y-3 rounded-3xl border bg-white p-6" data-testid="contact-form">
            {[["name", "Your name", "text", true], ["email", "Email", "email", true], ["phone", "Phone (optional)", "tel", false]].map(([k, l, t, r]) => <Input key={k} type={t} required={r} placeholder={l} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`contact-${k}-input`} />)}
            <Textarea required rows={5} placeholder="How can we help?" value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} data-testid="contact-message-input" />
            <label className="flex items-start gap-2 text-xs text-slate-600"><Checkbox checked={f.marketing_consent} onCheckedChange={(c) => setF({ ...f, marketing_consent: !!c })} />Optional: send me occasional offers by email.</label>
            <p className="text-xs text-slate-500">We use your details only to respond to your enquiry. See our <Link to="/privacy" className="underline">privacy policy</Link>.</p>
            <button className="w-full rounded-full py-3 text-sm font-semibold text-white" style={{ background: G }} data-testid="contact-submit-btn">Send message</button>
          </form>
        )}
      </div>
    </Shell>
  );
}

export function PolicyPage({ policyKey }) {
  const cfg = useOutletContext();
  const p = cfg.policies.find((x) => x.key === policyKey);
  return (
    <Shell eyebrow="Legal" title={p?.title || { privacy: "Privacy policy", cookies: "Cookie policy", terms: "Terms & conditions" }[policyKey]} testid={`site-policy-${policyKey}`}>
      {p ? <><p className="font-mono text-xs text-slate-400">Version {p.published_version} · effective {fmtDate(p.effective_date)}</p><p className="mt-4 max-w-3xl whitespace-pre-wrap leading-relaxed text-slate-700">{p.published_content}</p></>
        : <p className="text-slate-600" data-testid="policy-pending">This policy is being finalised. Please contact us with any questions.</p>}
    </Shell>
  );
}
