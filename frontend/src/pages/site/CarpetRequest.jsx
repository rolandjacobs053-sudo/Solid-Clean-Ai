import { useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import { CheckCircle2, Info, Loader2 } from "lucide-react";
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
import { CARPET_AREAS } from "@/pages/site/CarpetPage";
import { api, errMsg } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

const YN = [["yes", "Yes"], ["no", "No"]];
const YNS = [...YN, ["not_sure", "Not sure"]];
const TIMES = ["08:00", "10:00", "12:00", "14:00", "16:00"].map((t) => [t, t]);
const STEPS = ["Areas", "Condition & pets", "Photos", "Preferred time", "Your details", "Address"];
const TITLES = ["Which areas need cleaning?", "Carpet condition, pets & stains", "Upload pictures of your carpets", "Preferred date and time", "Your contact details", "Property address"];
const ACK = "Thank you for your carpet cleaning enquiry. Your request has been received and is awaiting review. We will assess your requirements and contact you with a quote. Your booking is not confirmed until we approve the appointment and confirm the details with you.";
const tomorrow = () => { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };
const Q = ({ l, children, testid }) => <div data-testid={testid}><Label className="text-sm font-semibold text-slate-900">{l}</Label>{children}</div>;
const F = ({ id, label, value, onChange, type = "text", area }) => (
  <div><Label htmlFor={id}>{label}</Label>{area
    ? <Textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} className="mt-2 rounded-xl" data-testid={`carpet-${id}`} />
    : <Input id={id} type={type} value={value} min={type === "date" ? tomorrow() : undefined} onChange={(e) => onChange(e.target.value)} className="mt-2 h-11 rounded-xl" data-testid={`carpet-${id}`} />}</div>
);

function AreasStep({ areas, setAreas, st, setSt, stairPhotos, setStairPhotos, pub }) {
  const toggle = (k) => { const n = { ...areas }; if (n[k]) delete n[k]; else n[k] = 1; setAreas(n); };
  return (
    <div className="space-y-6" data-testid="carpet-areas-step">
      <p className="text-sm text-slate-600">Select all the areas you would like cleaned, then tell us how many of each.</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {CARPET_AREAS.map(([k, n]) => (
          <button key={k} type="button" onClick={() => toggle(k)} data-testid={`carpet-area-${k}`} className={`overflow-hidden rounded-2xl border bg-white text-left transition-transform hover:-translate-y-0.5 ${areas[k] ? "border-[#023F00] ring-2 ring-[#023F00]" : "border-slate-200"}`}>
            <img src={`/carpet/${k}.jpg`} alt={n} className="h-24 w-full object-cover" /><span className="flex items-center gap-2 p-3 text-sm font-semibold text-[#023F00]">{areas[k] && <CheckCircle2 className="h-4 w-4" />}{n}</span>
          </button>
        ))}
      </div>
      {CARPET_AREAS.filter(([k]) => areas[k]).map(([k, , l]) => <Counter key={k} label={l} value={areas[k]} onChange={(v) => setAreas({ ...areas, [k]: v })} min={1} max={50} testid={`carpet-count-${k}`} />)}
      {areas.other && <F id="other-areas" label="Please describe the other carpeted areas" value={st.other_areas} onChange={(v) => setSt({ ...st, other_areas: v })} />}
      {areas.stairs && (
        <div className="space-y-5 rounded-3xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-5" data-testid="carpet-stairs-questions">
          <h3 className="font-display text-lg font-bold text-[#023F00]">About your stairs</h3>
          <div><Label htmlFor="steps">How many carpeted steps need cleaning?</Label><Input id="steps" type="number" min="1" max="200" inputMode="numeric" value={st.stairs_steps || ""} onChange={(e) => setSt({ ...st, stairs_steps: Math.max(0, Math.min(200, parseInt(e.target.value, 10) || 0)) })} className="mt-2 h-11 w-40 rounded-xl" data-testid="carpet-stairs-steps" /></div>
          <Q l="Is there a landing that also needs cleaning?"><Pills options={YN} value={st.stairs_landing} onChange={(v) => setSt({ ...st, stairs_landing: v })} testid="carpet-stairs-landing" /></Q>
          <PhotoUploader pub={pub} photos={stairPhotos} setPhotos={setStairPhotos} title="Pictures of the stairs and landing" text="Please upload pictures of the staircase and landing so we can assess the work." />
        </div>
      )}
    </div>
  );
}

function ConditionStep({ a, setA, notes, setNotes }) {
  const yn = (k, l, opts = YN) => <Q key={k} l={l} testid={`carpet-q-${k}`}><Pills options={opts} value={a[k]} onChange={(v) => setA({ ...a, [k]: v })} testid={`carpet-${k}`} /></Q>;
  return (
    <div className="space-y-8" data-testid="carpet-condition-step">
      <section className="space-y-5"><h3 className="eyebrow">Carpet condition</h3>{yn("visible_stains", "Are there any visible stains?")}{yn("heavily_soiled", "Are the carpets heavily soiled?", YNS)}
        <F id="concerns" label="Are there any particular marks or areas of concern?" area value={a.concerns || ""} onChange={(v) => setA({ ...a, concerns: v })} /></section>
      <section className="space-y-5"><h3 className="eyebrow">Pets</h3>{yn("pets", "Are there pets in the property?")}
        {a.pets === "yes" && <div className="space-y-5 rounded-3xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-5" data-testid="carpet-pet-questions">{yn("pet_hair", "Is there pet hair on the carpets?")}{yn("pet_urine", "Are there pet urine stains?")}{yn("pet_odour", "Are there unpleasant pet-related odours?")}
          <p className="text-xs text-slate-600">You can upload pictures of the affected areas in the next step.</p></div>}</section>
      <section className="space-y-5"><h3 className="eyebrow">Additional requirements</h3>{yn("stain_treatment", "Would you like to request stain treatment?")}{yn("odour_treatment", "Do you require treatment for pet-related odours?")}
        <F id="notes" label="Is there anything else we should know about the carpets?" area value={notes} onChange={setNotes} /></section>
      <p className="flex gap-3 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600" data-testid="carpet-treatment-disclaimer"><Info className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />Stain removal and pet odour treatments depend on the carpet material, the type of stain and its condition. We cannot guarantee that every stain or odour can be completely removed.</p>
    </div>
  );
}

function Aside({ areas, st, pref }) {
  const list = CARPET_AREAS.filter(([k]) => areas[k]).map(([k, n]) => `${n} × ${areas[k]}`);
  return (
    <aside className="sticky top-24 space-y-4 rounded-3xl border border-slate-200 bg-white p-6" data-testid="carpet-summary">
      <p className="eyebrow">Your carpet cleaning request</p>
      <ul className="space-y-1 text-sm">{list.length ? list.map((x) => <li key={x}>{x}</li>) : <li className="text-slate-400">No areas selected yet</li>}{areas.stairs && st.stairs_steps > 0 && <li>{st.stairs_steps} carpeted steps</li>}</ul>
      {pref.date && <p className="text-sm">Requested: <b>{new Date(`${pref.date}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} {pref.time}</b></p>}
      <div className="rounded-2xl bg-[#fbf9f1] p-4 text-sm text-[#023F00]"><b>Prices starting from £100.</b> We'll review your request and photos and send you an exact quote. Nothing is charged now.</div>
      <p className="text-xs text-slate-400">Your preferred time is a request only. Your booking is not confirmed until we approve the appointment.</p>
    </aside>
  );
}

export default function CarpetRequest() {
  const cfg = useOutletContext();
  const [params] = useSearchParams();
  const pub = `/public/${DEFAULT_SLUG}`;
  const first = CARPET_AREAS.some(([k]) => k === params.get("area")) ? { [params.get("area")]: 1 } : {};
  const [step, setStep] = useState(0);
  const [areas, setAreas] = useState(first);
  const [st, setSt] = useState({ stairs_steps: 0, stairs_landing: "", other_areas: "" });
  const [a, setA] = useState({});
  const [notes, setNotes] = useState("");
  const [photos, setPhotos] = useState([]);
  const [stairPhotos, setStairPhotos] = useState([]);
  const [pref, setPref] = useState({ date: "", time: "" });
  const [c, setC] = useState({ name: "", phone: "", email: "" });
  const [addr, setAddr] = useState({ address: "", postcode: "" });
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const uploading = [...photos, ...stairPhotos].some((p) => p.status === "uploading");
  const canNext = [Object.keys(areas).length > 0 && (!areas.stairs || st.stairs_steps > 0) && !uploading, !!a.visible_stains && !!a.heavily_soiled && !!a.pets, !uploading,
    !!pref.date && pref.date >= tomorrow() && !!pref.time, c.name.trim() && c.phone.length >= 6 && /\S+@\S+\.\S+/.test(c.email), addr.address.trim().length >= 5 && /^[A-Za-z]{1,2}\d/.test(addr.postcode.trim())][step];
  const hints = [areas.stairs && !st.stairs_steps ? "Tell us how many carpeted steps need cleaning" : "Select at least one area", "Answer the stains, soiling and pets questions", "Please wait for photos to finish uploading", "Choose a preferred date and time", "Add your full name, phone number and email", "Add the full property address and postcode"];

  const submit = async () => {
    setBusy(true);
    try {
      const answers = Object.fromEntries(Object.entries(a).filter(([k, v]) => v && (a.pets === "yes" || !k.startsWith("pet_"))));
      await api.post(`${pub}/carpet-quotes`, { areas, ...st, answers, notes, preferred_date: pref.date, preferred_time: pref.time, contact: c, ...addr, marketing_consent: consent,
        photos: [...stairPhotos, ...photos].filter((p) => p.status === "done").slice(0, 10).map(({ id, token }) => ({ id, token })) });
      setDone(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  if (done) return (
    <main className="mx-auto max-w-3xl px-4 py-20" data-testid="carpet-request-page">
      <div className="rounded-3xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-8 text-center sm:p-12" data-testid="carpet-request-confirmation">
        <CheckCircle2 className="mx-auto h-12 w-12 text-[#023F00]" /><p className="mx-auto mt-5 max-w-2xl text-lg text-slate-800">{ACK}</p>
        <Link to="/" className="mt-8 inline-block text-sm font-semibold text-[#023F00] underline">Back to the home page</Link>
      </div>
    </main>
  );
  return (
    <BookingShell prefix="carpet" eyebrow="Carpet cleaning · quote request" title={TITLES[step]} steps={STEPS} step={step} phone={cfg.business.phone} aside={<Aside areas={areas} st={st} pref={pref} />}>
      {step === 0 && <AreasStep areas={areas} setAreas={setAreas} st={st} setSt={setSt} stairPhotos={stairPhotos} setStairPhotos={setStairPhotos} pub={pub} />}
      {step === 1 && <ConditionStep a={a} setA={setA} notes={notes} setNotes={setNotes} />}
      {step === 2 && <div data-testid="carpet-photos-step"><PhotoUploader pub={pub} photos={photos} setPhotos={setPhotos} title=""
        text="Pictures help us see the condition of your carpets before we give you an accurate price. You can upload several pictures showing:" />
        <ul className="mt-3 grid gap-1 text-sm text-slate-700 sm:grid-cols-2">{["The overall carpeted area", "Stains and dirty patches", "Pet-related damage or marks", "Staircases and landings", "Any other areas requiring cleaning"].map((t) => <li key={t} className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-[#8F7E22]" />{t}</li>)}</ul></div>}
      {step === 3 && <div className="space-y-6" data-testid="carpet-time-step">
        <p className="text-sm text-slate-600">Choose a date and time that suits you. This is a request, not a guaranteed appointment - we'll confirm the time with your quote.</p>
        <div className="grid gap-6 sm:grid-cols-2"><F id="preferred-date" label="Preferred date" type="date" value={pref.date} onChange={(v) => setPref({ ...pref, date: v })} />
          <Q l="Preferred time"><Pills options={TIMES} value={pref.time} onChange={(v) => setPref({ ...pref, time: v })} testid="carpet-preferred-time" /></Q></div>
      </div>}
      {step === 4 && <div className="grid gap-4 sm:grid-cols-2" data-testid="carpet-details-step">
        <div className="sm:col-span-2"><F id="contact-name" label="Full name" value={c.name} onChange={(v) => setC({ ...c, name: v })} /></div>
        <F id="contact-phone" label="Phone number" type="tel" value={c.phone} onChange={(v) => setC({ ...c, phone: v })} />
        <F id="contact-email" label="Email address" type="email" value={c.email} onChange={(v) => setC({ ...c, email: v })} />
        <label className="flex items-start gap-3 text-sm text-slate-600 sm:col-span-2"><Checkbox checked={consent} onCheckedChange={(x) => setConsent(!!x)} data-testid="carpet-consent" />I'd like occasional updates and offers by email (optional).</label>
      </div>}
      {step === 5 && <div className="grid gap-4 sm:grid-cols-3" data-testid="carpet-address-step">
        <F id="postcode" label="Property postcode" value={addr.postcode} onChange={(v) => setAddr({ ...addr, postcode: v.toUpperCase() })} />
        <div className="sm:col-span-2"><F id="address" label="Full property address" value={addr.address} onChange={(v) => setAddr({ ...addr, address: v })} /></div>
        <p className="text-xs text-slate-500 sm:col-span-3">Submitting this form sends a quote request to Solid Clean Ltd. It does not confirm a booking.</p>
      </div>}
      <StepNav prefix="carpet" step={step} last={5} setStep={setStep} canNext={canNext} hint={hints[step]} nextLabel={step === 2 && !photos.length ? "Skip photos" : "Continue"}>
        {step === 5 && <Button disabled={!canNext || busy} onClick={submit} className="h-12 rounded-full bg-[#023F00] px-8 font-bold text-white hover:bg-[#8F7E22]" data-testid="carpet-submit-btn">
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Request my carpet cleaning quote</Button>}
      </StepNav>
    </BookingShell>
  );
}
