import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { ArrowDown, BadgeCheck, CalendarCheck, ClipboardList, ShieldCheck } from "lucide-react";
import { WalkthroughForm } from "@/components/site/WalkthroughForm";
import { DEFAULT_SLUG } from "@/lib/tenant";
import { CallBtn, G, GOLD } from "@/pages/site/SiteLayout";

const TYPES = [
  ["office", "Office cleaning", "Desks, meeting rooms, kitchens and washrooms kept clean for your team and visitors."],
  ["pub", "Pub cleaning", "Bar areas, seating, floors and washrooms cleaned around your opening hours."],
  ["restaurant", "Restaurant & café cleaning", "Dining areas, front of house and washrooms presented spotless for every service."],
  ["gym", "Gym & fitness centre cleaning", "Workout areas, studios, changing rooms and showers kept fresh and hygienic."],
  ["retail", "Retail shop cleaning", "Shop floors, fitting rooms and stockrooms that make a great first impression."],
  ["school", "Schools & educational premises", "Classrooms, halls, corridors and washrooms cleaned outside teaching hours."],
  ["medical", "Medical & healthcare premises", "Reception, waiting and consulting areas cleaned with care and attention to hygiene."],
  ["warehouse", "Warehouse & industrial premises", "Warehouse floors, offices and welfare facilities kept safe and tidy."],
  ["communal", "Communal area cleaning", "Entrances, stairwells, lifts and corridors in residential and commercial blocks."],
  ["other", "Other commercial premises", "Tell us about your premises and we'll arrange a visit to understand what you need."],
];
const INTRO = "Tell us about your business and cleaning requirements, and choose your preferred date and time for a site walkthrough. A member of the Solid Clean Ltd team will review your request and contact you to confirm the appointment. The walkthrough is free and carries no obligation to proceed.";
const go = () => document.getElementById("commercial-types")?.scrollIntoView({ behavior: "smooth" });

export default function CommercialPage() {
  const cfg = useOutletContext();
  const [type, setType] = useState(null);
  const pick = (k) => { setType(k); setTimeout(() => document.getElementById("walkthrough-form")?.scrollIntoView({ behavior: "smooth" }), 50); };
  const t = TYPES.find(([k]) => k === type);
  return (
    <main data-testid="commercial-page">
      <section className="relative overflow-hidden text-white" style={{ background: G }}>
        <img src="/commercial/office.jpg" alt="" className="absolute inset-0 h-full w-full object-cover opacity-20" />
        <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: "#d9c56a" }}>Commercial cleaning · London & Surrey</p>
          <h1 className="mt-5 max-w-3xl text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">Commercial cleaning, planned around your premises.</h1>
          <p className="mt-6 max-w-2xl text-base text-white/80 sm:text-lg">{INTRO}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <button onClick={go} className="inline-flex items-center gap-2 rounded-full px-7 py-4 text-sm font-bold uppercase tracking-wide text-[#023F00] transition-transform hover:-translate-y-0.5" style={{ background: "#d9c56a" }} data-testid="commercial-hero-walkthrough-btn">Book a free site walkthrough<ArrowDown className="h-4 w-4" /></button>
            {cfg.business.phone && <CallBtn phone={cfg.business.phone} className="!border-white/60 !text-white hover:!bg-white/10" testid="commercial-call-btn" />}
          </div>
          <div className="mt-10 flex flex-wrap gap-6 text-sm text-white/80">
            {[[BadgeCheck, "Free, no-obligation walkthrough"], [ShieldCheck, "Fully insured"], [ClipboardList, "Quotation tailored to your premises"]].map(([I, x]) => <span key={x} className="flex items-center gap-2"><I className="h-4 w-4" style={{ color: "#d9c56a" }} />{x}</span>)}
          </div>
        </div>
      </section>
      <section id="commercial-types" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold sm:text-3xl" style={{ color: G }}>Choose your type of premises</h2>
        <p className="mt-2 text-slate-600">Select your premises to open a short form tailored to your business.</p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {TYPES.map(([k, name, desc]) => (
            <button key={k} onClick={() => pick(k)} className={`group flex flex-col justify-start overflow-hidden rounded-3xl border bg-white text-left transition-transform hover:-translate-y-1 ${type === k ? "border-[#023F00] ring-2 ring-[#023F00]" : "border-slate-200"}`} data-testid={`commercial-type-${k}`}>
              <div className="overflow-hidden"><img src={`/commercial/${k}.jpg`} alt={name} className="h-40 w-full object-cover transition-transform duration-500 group-hover:scale-105" /></div>
              <div className="p-5"><h3 className="font-display font-semibold" style={{ color: G }}>{name}</h3><p className="mt-2 text-sm text-slate-600">{desc}</p>
                <span className="mt-3 inline-block font-mono text-[11px] font-semibold uppercase tracking-wider" style={{ color: GOLD }}>Request a free walkthrough →</span></div>
            </button>
          ))}
        </div>
      </section>
      <section id="walkthrough-form" className="bg-slate-50 py-16">
        <div className="mx-auto max-w-4xl px-4 sm:px-6">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: GOLD }}><CalendarCheck className="mr-1 inline h-4 w-4" />Free site walkthrough</p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight" style={{ color: G }}>Book a free site walkthrough</h2>
          <p className="mt-3 text-slate-600">{INTRO}</p>
          <div className="mt-8">{t ? <WalkthroughForm key={t[0]} pub={`/public/${DEFAULT_SLUG}`} type={t[0]} typeName={t[1]} />
            : <button onClick={go} className="w-full rounded-3xl border-2 border-dashed border-slate-300 p-10 text-slate-600 hover:border-[#8F7E22]" data-testid="commercial-choose-type-prompt">First, choose your type of premises above</button>}</div>
        </div>
      </section>
    </main>
  );
}
