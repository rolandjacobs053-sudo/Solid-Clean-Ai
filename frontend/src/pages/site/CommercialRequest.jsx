import { useEffect, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Counter } from "@/components/quote/Controls";
import { Pills } from "@/components/quote/BookingSteps";
import { BookingShell, StepNav } from "@/components/quote/BookingShell";
import { PhotoUploader } from "@/components/quote/PhotoUploader";
import { api, errMsg } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

export const TYPES = [
  ["office", "Office"], ["pub", "Pub"], ["restaurant", "Restaurant / café"], ["gym", "Gym / fitness centre"], ["retail", "Shop / retail space"],
  ["school", "School / educational"], ["medical", "Medical / healthcare"], ["warehouse", "Warehouse / industrial"], ["communal", "Communal areas / shared building"], ["other", "Other commercial premises"],
];
const EXTRA = {
  office: [["workstations", "Number of desks / workstations"], ["meeting_rooms", "Meeting rooms"]],
  pub: [["bar_areas", "Bar and seating areas"], ["cellar", "Cellar or back-of-house areas to include?"]],
  restaurant: [["dining", "Dining area size / covers"], ["kitchen", "Kitchen or food-preparation areas to be cleaned (describe)"]],
  gym: [["workout", "Workout / studio areas"], ["changing", "Changing rooms and showers"]],
  retail: [["shop_floor", "Shop floor size"], ["stockroom", "Stockroom or fitting rooms"]],
  school: [["classrooms", "Number of classrooms"], ["halls", "Halls, canteen or sports areas"]],
  medical: [["treatment_rooms", "Consulting / treatment rooms"], ["clinical_notes", "Any specific hygiene requirements"]],
  warehouse: [["warehouse_area", "Warehouse floor area"], ["office_area", "Offices / welfare areas included"]],
  communal: [["blocks", "Number of blocks / entrances"], ["stairs_lifts", "Stairwells, lifts and corridors"]],
  other: [["premises_desc", "Describe your premises"]],
};
const CLEAN_TYPES = [["regular", "Regular contract cleaning"], ["deep", "One-off deep clean"], ["other", "Other (describe below)"]];
const FREQ = [["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"], ["one_off", "One-off"], ["other", "Other"]];
const CONDITION = [["good", "Well maintained"], ["average", "Average"], ["needs_attention", "Needs extra attention"]];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TIMES = [["early_morning", "Early morning"], ["daytime", "Daytime"], ["evening", "Evening"], ["overnight", "Overnight"]];
const VISIT_TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];
const COUNTS = [["floors", "Floors"], ["rooms", "Rooms / main areas"], ["toilets", "Toilets & washrooms"], ["kitchens", "Kitchens / staff rooms"]];
export const FIELD_LABELS = Object.fromEntries([...COUNTS, ...Object.values(EXTRA).flat(), ["cleaning_type", "Type of cleaning required"], ["size", "Size of the property"],
  ["other_areas", "Other relevant areas"], ["attention", "Areas requiring particular attention"], ["special", "Additional cleaning requirements"], ["condition", "Current condition"], ["flooring", "Flooring types"]]);
const STEPS = ["Premises", "Requirements", "Photos", "Site visit", "Your details", "Address"];
const TITLES = ["What type of premises?", "Your cleaning requirements", "Upload Photos of Your Premises", "When Would You Like Us to Visit?", "Your contact details", "Premises address"];
const CONFIRM = "Thank you for contacting Solid Clean Ltd. We have received your request for a free commercial cleaning site walkthrough. Our team will review your details and contact you to confirm a suitable date and time. The walkthrough is free and there is no obligation to proceed.";
const tomorrow = () => { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };
const label = (list, k) => list.find(([x]) => x === k)?.[1];

const F = ({ id, label: l, value, onChange, type = "text", area }) => (
  <div><Label htmlFor={id}>{l}</Label>{area
    ? <Textarea id={id} value={value || ""} onChange={(e) => onChange(e.target.value)} className="mt-2 rounded-xl" data-testid={`wt-${id}`} />
    : <Input id={id} type={type} value={value || ""} min={type === "date" ? tomorrow() : undefined} onChange={(e) => onChange(e.target.value)} className="mt-2 h-11 rounded-xl" data-testid={`wt-${id}`} />}</div>
);
const Q = ({ l, children }) => <div><Label className="eyebrow">{l}</Label>{children}</div>;

function Aside({ type, det, sch, visit }) {
  const rows = [["Premises", label(TYPES, type)], ["Cleaning", label(CLEAN_TYPES, det.cleaning_type)], ["Frequency", label(FREQ, sch.frequency)], ["Size", det.size],
    ["Visit requested", visit.preferred_date && `${new Date(visit.preferred_date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} ${visit.preferred_time}`]];
  return (
    <aside className="sticky top-24 rounded-3xl border border-slate-200 bg-white p-6" data-testid="wt-summary">
      <p className="eyebrow">Your free site visit</p>
      <dl className="mt-4 space-y-2 text-sm">{rows.map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium">{v || "-"}</dd></div>)}</dl>
      <div className="mt-5 rounded-2xl bg-[#fbf9f1] p-4 text-sm text-[#023F00]"><b>Free · No obligation · No payment.</b> We visit your premises, understand your requirements and then prepare a tailored quotation.</div>
      <p className="mt-4 text-xs text-slate-400">Your requested time is not confirmed until our team contacts you.</p>
    </aside>
  );
}

export default function CommercialRequest() {
  const cfg = useOutletContext();
  const [params] = useSearchParams();
  const pub = `/public/${DEFAULT_SLUG}`;
  const [step, setStep] = useState(0);
  const [type, setType] = useState(params.get("type") || "");
  const [det, setDet] = useState({ floors: 1, rooms: 1, toilets: 1, kitchens: 0 });
  const [sch, setSch] = useState({ frequency: "", days: [], time: "", start_date: "", notes: "" });
  const [visit, setVisit] = useState({ preferred_date: "", preferred_time: "", alt_date: "", alt_time: "", access_info: "" });
  const [c, setC] = useState({ name: "", phone: "", email: "", business_name: "" });
  const [addr, setAddr] = useState({ address: "", postcode: "" });
  const [photos, setPhotos] = useState([]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  useEffect(() => { if (params.get("type")) setStep(1); }, [params]);
  const d = (k) => (v) => setDet({ ...det, [k]: v });
  const canNext = [!!type, !!det.cleaning_type && !!sch.frequency, !photos.some((p) => p.status === "uploading"), !!visit.preferred_date && !!visit.preferred_time,
    c.name && c.business_name && c.phone.length >= 6 && /\S+@\S+\.\S+/.test(c.email), addr.address.trim().length >= 5 && /^[A-Za-z]{1,2}\d/.test(addr.postcode.trim())][step];
  const hints = ["Choose your type of premises", "Choose the type of cleaning and how often", "Please wait for photos to finish uploading", "Choose a preferred date and time", "Add your business name, name, phone and email", "Add the full premises address and postcode"];

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`${pub}/walkthroughs`, { establishment: type, business_name: c.business_name, contact: { name: c.name, phone: c.phone, email: c.email }, ...addr, details: det,
        schedule: { ...sch, kind: sch.frequency === "one_off" || det.cleaning_type === "deep" ? "one_off" : "ongoing" }, visit, marketing_consent: consent,
        photos: photos.filter((p) => p.status === "done").map(({ id, token }) => ({ id, token })) });
      setDone(true);
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  if (done) return (
    <main className="mx-auto max-w-3xl px-4 py-20" data-testid="wt-page">
      <div className="rounded-3xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-8 text-center sm:p-12" data-testid="walkthrough-confirmation">
        <CheckCircle2 className="mx-auto h-12 w-12 text-[#023F00]" /><p className="mx-auto mt-5 max-w-2xl text-lg text-slate-800">{CONFIRM}</p>
        <Link to="/" className="mt-8 inline-block text-sm font-semibold text-[#023F00] underline">Back to the home page</Link>
      </div>
    </main>
  );
  return (
    <BookingShell prefix="wt" eyebrow="Commercial cleaning · free site walkthrough" title={TITLES[step]} steps={STEPS} step={step} phone={cfg.business.phone} aside={<Aside type={type} det={det} sch={sch} visit={visit} />}>
      {step === 0 && <div className="grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="wt-type-options">
        {TYPES.map(([k, n]) => <button key={k} type="button" onClick={() => setType(k)} data-testid={`wt-type-${k}`} className={`overflow-hidden rounded-2xl border bg-white text-left transition-transform hover:-translate-y-0.5 ${type === k ? "border-[#023F00] ring-2 ring-[#023F00]" : "border-slate-200"}`}>
          <img src={`/commercial/${k}.jpg`} alt={n} className="h-24 w-full object-cover" /><span className="block p-3 text-sm font-semibold text-[#023F00]">{n}</span></button>)}
      </div>}
      {step === 1 && <div className="space-y-7" data-testid={`wt-requirements-${type}`}>
        <Q l="Type of cleaning required"><Pills options={CLEAN_TYPES} value={det.cleaning_type} onChange={d("cleaning_type")} testid="wt-cleaning-type" /></Q>
        <Q l="How often?"><Pills options={FREQ} value={sch.frequency} onChange={(v) => setSch({ ...sch, frequency: v })} testid="wt-frequency" /></Q>
        <F id="size" label="Size of the property (approx. sq ft or m², if known)" value={det.size} onChange={d("size")} />
        <div className="grid gap-3">{COUNTS.map(([k, l]) => <Counter key={k} label={l} value={det[k]} onChange={d(k)} max={50} testid={`wt-${k}-count`} />)}</div>
        <div className="grid gap-4 sm:grid-cols-2">{(EXTRA[type] || []).map(([k, l]) => <F key={k} id={k} label={l} value={det[k]} onChange={d(k)} />)}
          <F id="other_areas" label="Other relevant areas (e.g. reception, corridors, stairs)" value={det.other_areas} onChange={d("other_areas")} />
          <F id="flooring" label="Flooring types (e.g. carpet, vinyl, tiles)" value={det.flooring} onChange={d("flooring")} /></div>
        <Q l="Current condition"><Pills options={CONDITION} value={det.condition} onChange={d("condition")} testid="wt-condition" /></Q>
        <Q l="Which days would suit you?"><div className="mt-3 flex flex-wrap gap-2">{DAYS.map((x) => <button key={x} type="button" data-testid={`wt-day-${x}`} onClick={() => setSch({ ...sch, days: sch.days.includes(x) ? sch.days.filter((y) => y !== x) : [...sch.days, x] })}
          className={`rounded-full border px-4 py-2 text-sm ${sch.days.includes(x) ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-200 bg-white"}`}>{x}</button>)}</div></Q>
        <Q l="Preferred cleaning time"><Pills options={TIMES} value={sch.time} onChange={(v) => setSch({ ...sch, time: v })} testid="wt-time" /></Q>
        <div className="grid gap-4 sm:grid-cols-2"><F id="start" label="When would you like the cleaning to start?" type="date" value={sch.start_date} onChange={(v) => setSch({ ...sch, start_date: v })} /></div>
        <F id="special" label="Any additional cleaning requirements" area value={det.special} onChange={d("special")} />
        <F id="schedule-notes" label="Anything else about scheduling" area value={sch.notes} onChange={(v) => setSch({ ...sch, notes: v })} />
      </div>}
      {step === 2 && <PhotoUploader pub={pub} photos={photos} setPhotos={setPhotos} title="" text="Photographs help us understand your premises before the visit. Add photos of the main areas, washrooms, kitchens and anywhere that needs particular attention. Photos are optional." />}
      {step === 3 && <div className="space-y-6" data-testid="wt-visit-step">
        <p className="text-sm text-slate-600">Choose a date and time that suits you. This is a request - we'll check our availability and contact you to confirm.</p>
        <div className="grid gap-6 sm:grid-cols-2">
          <F id="visit-date" label="Preferred date" type="date" value={visit.preferred_date} onChange={(v) => setVisit({ ...visit, preferred_date: v })} />
          <Q l="Preferred time"><Pills options={VISIT_TIMES.map((t) => [t, t])} value={visit.preferred_time} onChange={(v) => setVisit({ ...visit, preferred_time: v })} testid="wt-visit-time" /></Q>
          <F id="alt-date" label="Alternative date (optional)" type="date" value={visit.alt_date} onChange={(v) => setVisit({ ...visit, alt_date: v })} />
          <Q l="Alternative time (optional)"><Pills options={VISIT_TIMES.map((t) => [t, t])} value={visit.alt_time} onChange={(v) => setVisit({ ...visit, alt_time: v })} testid="wt-alt-time" /></Q>
        </div>
        <F id="access-info" label="How should we arrange access to the premises for the visit?" area value={visit.access_info} onChange={(v) => setVisit({ ...visit, access_info: v })} />
      </div>}
      {step === 4 && <div className="grid gap-4 sm:grid-cols-2" data-testid="wt-details-step">
        <F id="business-name" label="Business or organisation name" value={c.business_name} onChange={(v) => setC({ ...c, business_name: v })} />
        <F id="contact-name" label="Full name" value={c.name} onChange={(v) => setC({ ...c, name: v })} />
        <F id="contact-email" label="Email address" type="email" value={c.email} onChange={(v) => setC({ ...c, email: v })} />
        <F id="contact-phone" label="Phone number" type="tel" value={c.phone} onChange={(v) => setC({ ...c, phone: v })} />
        <label className="flex items-start gap-3 text-sm text-slate-600 sm:col-span-2"><Checkbox checked={consent} onCheckedChange={(x) => setConsent(!!x)} data-testid="wt-consent" />I'd like occasional updates and offers by email (optional).</label>
      </div>}
      {step === 5 && <div className="grid gap-4 sm:grid-cols-3" data-testid="wt-address-step">
        <div className="sm:col-span-2"><F id="address" label="Full premises address" value={addr.address} onChange={(v) => setAddr({ ...addr, address: v })} /></div>
        <F id="postcode" label="Postcode" value={addr.postcode} onChange={(v) => setAddr({ ...addr, postcode: v.toUpperCase() })} />
      </div>}
      <StepNav prefix="wt" step={step} last={5} setStep={setStep} canNext={canNext} hint={hints[step]} nextLabel={step === 2 && !photos.length ? "Skip photos" : "Continue"}>
        {step === 5 && <Button disabled={!canNext || busy} onClick={submit} className="h-12 rounded-full bg-[#023F00] px-8 font-bold uppercase tracking-wide text-white hover:bg-[#8F7E22]" data-testid="wt-submit-btn">
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Book a free site walkthrough</Button>}
      </StepNav>
    </BookingShell>
  );
}
