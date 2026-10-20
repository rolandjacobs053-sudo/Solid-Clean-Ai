import { Link, useOutletContext } from "react-router-dom";
import { Camera, CheckCircle2, ClipboardCheck, CreditCard, Info, MessageSquareText, ShieldCheck } from "lucide-react";
import { CallBtn, G, GOLD } from "@/pages/site/SiteLayout";

export const CARPET_AREAS = [
  ["living_room", "Living room carpets", "Number of living rooms"], ["bedroom", "Bedroom carpets", "Number of bedrooms"], ["hallway", "Hallway carpets", "Number of hallways"],
  ["stairs", "Carpeted stairs", "Number of staircases"], ["landing", "Carpeted landings", "Number of landings"], ["office", "Office carpets", "Number of office rooms / areas"],
  ["commercial", "Commercial carpets", "Number of commercial areas"], ["other", "Other carpeted areas", "Number of other areas"],
];
const INCLUDED = ["Deep cleaning with a professional, commercial carpet cleaning machine", "Pre-treatment of high-traffic and heavily used areas", "Targeted stain treatment, on request",
  "Pet hair removal and pet odour treatment, on request", "Carpeted stairs and landings", "Homes, offices and commercial premises"];
const STEPS = [[MessageSquareText, "You send a request", "Choose the areas, answer a few questions, upload photos and pick a preferred date and time."], [ClipboardCheck, "We review it", "Our team looks at your details and pictures to assess the work."],
  [CreditCard, "We send your quote", "You receive the price and service details by email. Prices start from £100."], [CheckCircle2, "You accept the quote", "Review the price and accept it online with secure card payment."],
  [ShieldCheck, "We approve & confirm", "Your booking is only confirmed once we approve the appointment."]];
const CTA = "inline-flex items-center justify-center rounded-full px-7 py-3.5 text-sm font-bold uppercase tracking-wide text-white transition-transform hover:-translate-y-0.5";

export const PriceNote = ({ className = "" }) => (
  <div className={`rounded-3xl border-2 p-6 ${className}`} style={{ borderColor: GOLD, background: "#fbf9f1" }} data-testid="carpet-price-block">
    <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: GOLD }}>Professional Carpet Cleaning</p>
    <p className="mt-2 text-3xl font-extrabold tracking-tight" style={{ color: G }}>Prices starting from £100</p>
    <p className="mt-2 text-sm text-slate-700">£100 is our starting price, not a fixed price for every job. The final price will depend on the number of areas, the size of the carpets, the number of stairs, their condition and any specialist treatment required.</p>
  </div>
);

export default function CarpetPage() {
  const b = useOutletContext().business;
  return (
    <main data-testid="carpet-page">
      <section style={{ background: "#f7f4fb" }}>
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:px-8 lg:py-20">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] rise" style={{ color: GOLD }}>Carpet cleaning · homes & businesses</p>
            <h1 className="mt-4 text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl rise rise-1" style={{ color: G }}>Professional Carpet Cleaning</h1>
            <p className="mt-6 max-w-xl text-base text-slate-700 sm:text-lg rise rise-2" data-testid="carpet-description">Carpets can harbour allergens, dust and dirt, affecting the overall cleanliness and air quality of your space. Our professional carpet cleaning service is designed to lift deep-seated dirt, stains and allergens, leaving your carpets fresh, soft and revitalised.</p>
            <div className="mt-8 flex flex-wrap gap-3 rise rise-3">
              <Link to="/carpet-cleaning/request" className={CTA} style={{ background: G }} data-testid="carpet-request-btn">Request a carpet cleaning quote</Link>
              {b.phone && <CallBtn phone={b.phone} testid="carpet-call-btn" />}
            </div>
          </div>
          <img src="/carpet/hero.jpg" alt="Professional carpet cleaner deep-cleaning a carpet with a commercial carpet cleaning machine" className="aspect-[4/3] w-full rounded-[2rem] object-cover shadow-2xl" data-testid="carpet-hero-img" />
        </div>
      </section>
      <section className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:px-8">
        <div>
          <h2 className="text-2xl font-bold sm:text-3xl" style={{ color: G }}>What's included</h2>
          <ul className="mt-6 space-y-3" data-testid="carpet-included">{INCLUDED.map((t) => <li key={t} className="flex gap-3 text-slate-700"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" style={{ color: GOLD }} />{t}</li>)}</ul>
          <p className="mt-6 flex gap-3 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600" data-testid="carpet-disclaimer"><Info className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />Results of stain removal and pet odour treatments depend on the carpet material, the type of stain and its condition. We always aim for the best possible result, but we cannot guarantee that every stain or odour can be completely removed.</p>
        </div>
        <div className="space-y-6"><PriceNote /><div className="flex items-start gap-3 rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-700"><Camera className="h-6 w-6 shrink-0" style={{ color: G }} />Upload pictures of your carpets with your request - the overall area, stains, pet marks, stairs and landings - so we can give you an accurate quote.</div></div>
      </section>
      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold sm:text-3xl" style={{ color: G }}>Carpeted areas we clean</h2>
        <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4" data-testid="carpet-areas-grid">
          {CARPET_AREAS.map(([k, n]) => (
            <Link key={k} to={`/carpet-cleaning/request?area=${k}`} className="group overflow-hidden rounded-3xl border border-slate-200 bg-white transition-transform hover:-translate-y-1" data-testid={`carpet-area-card-${k}`}>
              <img src={`/carpet/${k}.jpg`} alt={n} loading="lazy" className="aspect-[4/3] w-full object-cover" /><span className="block p-4 text-sm font-semibold" style={{ color: G }}>{n}</span>
            </Link>
          ))}
        </div>
      </section>
      <section className="py-16 text-white" style={{ background: G }}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold sm:text-3xl">How carpet cleaning booking works</h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-5" data-testid="carpet-process">
            {STEPS.map(([I, t, d], i) => <div key={t} className="border-l border-white/20 pl-5"><span className="font-mono text-xs text-white/50">Step {i + 1}</span><I className="mt-3 h-6 w-6" style={{ color: "#d9c56a" }} /><h3 className="mt-3 font-display text-lg font-semibold">{t}</h3><p className="text-sm text-white/70">{d}</p></div>)}
          </div>
          <p className="mt-10 max-w-3xl text-sm text-white/80">Your preferred date and time is a request, not a guaranteed appointment. Submitting the form does not confirm a booking.</p>
          <Link to="/carpet-cleaning/request" className={`${CTA} mt-8 text-[#023F00]`} style={{ background: "#d9c56a" }} data-testid="carpet-request-btn-bottom">Request a carpet cleaning quote</Link>
        </div>
      </section>
    </main>
  );
}
