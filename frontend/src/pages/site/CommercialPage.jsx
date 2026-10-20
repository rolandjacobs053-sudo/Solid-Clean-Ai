import { Link, useOutletContext } from "react-router-dom";
import { ArrowRight, BadgeCheck, CalendarCheck, ClipboardList, Search, ShieldCheck } from "lucide-react";
import { CallBtn, G, GOLD } from "@/pages/site/SiteLayout";

const TYPES = [
  ["office", "Office cleaning", "Desks, meeting rooms, kitchens and washrooms kept clean for your team and visitors."],
  ["pub", "Pub cleaning", "Bar areas, seating, floors and washrooms cleaned around your opening hours."],
  ["restaurant", "Restaurant & café cleaning", "Dining areas, front of house and washrooms presented spotless for every service."],
  ["gym", "Gym & fitness centre cleaning", "Workout areas, studios, changing rooms and showers kept fresh and hygienic."],
  ["retail", "Shop & retail space cleaning", "Shop floors, fitting rooms and stockrooms that make a great first impression."],
  ["school", "Schools & educational premises", "Classrooms, halls, corridors and washrooms cleaned outside teaching hours."],
  ["medical", "Medical & healthcare premises", "Reception, waiting and consulting areas cleaned with care and attention to hygiene."],
  ["warehouse", "Warehouse & industrial premises", "Warehouse floors, offices and welfare facilities kept safe and tidy."],
  ["communal", "Communal areas & shared buildings", "Entrances, stairwells, lifts and corridors in residential and commercial blocks."],
  ["other", "Other commercial premises", "Tell us about your premises and we'll arrange a visit to understand what you need."],
];
const INTRO = "Tell us about your business and cleaning requirements, and choose your preferred date and time for a site walkthrough. A member of the Solid Clean Ltd team will review your request and contact you to confirm the appointment. The walkthrough is free and carries no obligation to proceed.";
const HOW = [[ClipboardList, "1. Tell us about your premises", "Choose your type of premises, describe your requirements and add photos."],
  [CalendarCheck, "2. Free site walkthrough", "Pick a preferred date and time. We'll confirm the visit and walk the premises with you."],
  [Search, "3. Tailored quotation", "After the visit we prepare a quotation based on your premises, schedule and requirements."]];
const WalkBtn = ({ type, testid, light }) => (
  <Link to={`/commercial-cleaning/request${type ? `?type=${type}` : ""}`} data-testid={testid}
    className={`inline-flex items-center gap-2 rounded-full px-7 py-4 text-sm font-bold uppercase tracking-wide transition-transform hover:-translate-y-0.5 ${light ? "text-[#023F00]" : "text-white"}`} style={{ background: light ? "#d9c56a" : G }}>
    Book a free site walkthrough<ArrowRight className="h-4 w-4" /></Link>
);

export default function CommercialPage() {
  const cfg = useOutletContext();
  return (
    <main data-testid="commercial-page">
      <section className="relative overflow-hidden text-white" style={{ background: G }}>
        <img src="/commercial/office.jpg" alt="" className="absolute inset-0 h-full w-full object-cover opacity-20" />
        <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: "#d9c56a" }}>Commercial cleaning · London & Surrey</p>
          <h1 className="mt-5 max-w-3xl text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">Commercial cleaning, planned around your premises.</h1>
          <p className="mt-6 max-w-2xl text-base text-white/80 sm:text-lg">{INTRO}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <WalkBtn light testid="commercial-hero-walkthrough-btn" />
            {cfg.business.phone && <CallBtn phone={cfg.business.phone} className="!border-white/60 !text-white hover:!bg-white/10" testid="commercial-call-btn" />}
          </div>
          <div className="mt-10 flex flex-wrap gap-6 text-sm text-white/80">
            {[[BadgeCheck, "Free, no-obligation walkthrough"], [ShieldCheck, "Fully insured"], [ClipboardList, "Quotation tailored to your premises"]].map(([I, x]) => <span key={x} className="flex items-center gap-2"><I className="h-4 w-4" style={{ color: "#d9c56a" }} />{x}</span>)}
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8" data-testid="commercial-how">
        <div className="grid gap-5 md:grid-cols-3">
          {HOW.map(([I, t, x]) => <div key={t} className="rounded-3xl border border-slate-200 bg-white p-7"><I className="h-7 w-7" style={{ color: GOLD }} /><h3 className="mt-4 font-display text-lg font-bold" style={{ color: G }}>{t}</h3><p className="mt-2 text-sm text-slate-600">{x}</p></div>)}
        </div>
      </section>
      <section id="commercial-types" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold sm:text-3xl" style={{ color: G }}>The premises we clean</h2>
        <p className="mt-2 text-slate-600">Select your type of premises to request a free site walkthrough.</p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {TYPES.map(([k, name, desc]) => (
            <Link key={k} to={`/commercial-cleaning/request?type=${k}`} className="group flex flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white transition-transform hover:-translate-y-1" data-testid={`commercial-type-${k}`}>
              <div className="overflow-hidden"><img src={`/commercial/${k}.jpg`} alt={name} className="h-40 w-full object-cover transition-transform duration-500 group-hover:scale-105" /></div>
              <div className="flex flex-1 flex-col p-5"><h3 className="font-display font-semibold" style={{ color: G }}>{name}</h3><p className="mt-2 flex-1 text-sm text-slate-600">{desc}</p>
                <span className="mt-3 font-mono text-[11px] font-semibold uppercase tracking-wider" style={{ color: GOLD }}>Request a free walkthrough →</span></div>
            </Link>
          ))}
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-6 rounded-[2rem] border-2 p-8 sm:p-12 lg:flex-row lg:items-center" style={{ borderColor: GOLD, background: "#fbf9f1" }}>
          <div><h2 className="text-2xl font-extrabold sm:text-3xl" style={{ color: G }}>Ready to talk about your premises?</h2><p className="mt-2 max-w-xl text-slate-600">The walkthrough is free and there is no obligation to proceed.</p></div>
          <WalkBtn testid="commercial-bottom-walkthrough-btn" />
        </div>
      </section>
    </main>
  );
}
