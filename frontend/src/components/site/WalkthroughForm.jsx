import { useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Pills } from "@/components/quote/BookingSteps";
import { PhotoUploader } from "@/components/quote/PhotoUploader";
import { api, errMsg } from "@/lib/api";

const EXTRA = {
  office: [["workstations", "Number of desks / workstations"], ["meeting_rooms", "Meeting rooms"]],
  pub: [["bar_areas", "Bar and seating areas"], ["cellar", "Cellar or back-of-house areas to include?"]],
  restaurant: [["dining", "Dining area size / covers"], ["kitchen", "Commercial kitchen to be cleaned? (describe)"]],
  gym: [["workout", "Workout / studio areas"], ["changing", "Changing rooms and showers"]],
  retail: [["shop_floor", "Shop floor size"], ["stockroom", "Stockroom or fitting rooms"]],
  school: [["classrooms", "Number of classrooms"], ["halls", "Halls, canteen or sports areas"]],
  medical: [["treatment_rooms", "Consulting / treatment rooms"], ["clinical_notes", "Any specific clinical cleaning requirements"]],
  warehouse: [["warehouse_area", "Warehouse floor area"], ["office_area", "Offices / welfare areas included"]],
  communal: [["blocks", "Number of blocks / entrances"], ["stairs_lifts", "Stairwells, lifts and corridors"]],
  other: [["premises_desc", "Describe your premises"]],
};
const COMMON = [["floor_area", "Approximate floor area (if known)"], ["floors", "Number of floors"], ["rooms", "Number of rooms / main areas"], ["toilets", "Toilets and washrooms"],
  ["kitchens", "Kitchens or staff rooms"], ["flooring", "Flooring types (e.g. carpet, vinyl, tiles)"]];
const CONDITION = [["good", "Well maintained"], ["average", "Average"], ["needs_attention", "Needs extra attention"]];
const FREQ = [["daily", "Daily"], ["several_weekly", "Several times a week"], ["weekly", "Weekly"], ["fortnightly", "Fortnightly"], ["monthly", "Monthly"]];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TIMES = [["early_morning", "Early morning"], ["daytime", "Daytime"], ["evening", "Evening"], ["overnight", "Overnight"]];
const VISIT_TIMES = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"];
const tomorrow = () => { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };

const Sec = ({ title, children }) => <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 sm:p-8"><h3 className="font-display text-xl font-bold text-[#023F00]">{title}</h3>{children}</section>;
const F = ({ id, label, value, onChange, type = "text", area }) => (
  <div><Label htmlFor={id}>{label}</Label>{area
    ? <Textarea id={id} value={value || ""} onChange={(e) => onChange(e.target.value)} className="mt-2 rounded-xl" data-testid={`wt-${id}`} />
    : <Input id={id} type={type} value={value || ""} min={type === "date" ? tomorrow() : undefined} onChange={(e) => onChange(e.target.value)} className="mt-2 h-11 rounded-xl" data-testid={`wt-${id}`} />}</div>
);

export function WalkthroughForm({ pub, type, typeName }) {
  const [c, setC] = useState({ name: "", phone: "", email: "" });
  const [biz, setBiz] = useState({ business_name: "", address: "", postcode: "" });
  const [det, setDet] = useState({});
  const [sch, setSch] = useState({ kind: "ongoing", frequency: "", days: [], time: "", start_date: "", notes: "" });
  const [visit, setVisit] = useState({ preferred_date: "", preferred_time: "", alt_date: "", alt_time: "", access_info: "" });
  const [photos, setPhotos] = useState([]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const d = (k) => (v) => setDet({ ...det, [k]: v });
  const ok = c.name && c.phone.length >= 6 && /\S+@\S+\.\S+/.test(c.email) && biz.business_name && biz.address.length >= 5 && biz.postcode && visit.preferred_date && visit.preferred_time && !photos.some((p) => p.status === "uploading");

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`${pub}/walkthroughs`, { establishment: type, ...biz, contact: c, details: det, schedule: sch, visit, marketing_consent: consent,
        photos: photos.filter((p) => p.status === "done").map(({ id, token }) => ({ id, token })) });
      setDone(true);
      window.scrollTo({ top: document.getElementById("walkthrough-form")?.offsetTop - 80, behavior: "smooth" });
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  if (done) return (
    <div className="rounded-3xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-8 text-center sm:p-12" data-testid="walkthrough-confirmation">
      <CheckCircle2 className="mx-auto h-12 w-12 text-[#023F00]" />
      <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-800">Thank you for contacting Solid Clean Ltd. We have received your request for a free commercial cleaning site walkthrough. Our team will review your details and contact you to confirm a suitable date and time. The walkthrough is free and there is no obligation to proceed.</p>
    </div>
  );
  return (
    <div className="space-y-6" data-testid="walkthrough-form-fields">
      <Sec title={`Business details - ${typeName}`}>
        <div className="grid gap-4 sm:grid-cols-2">
          <F id="business-name" label="Business or organisation name" value={biz.business_name} onChange={(v) => setBiz({ ...biz, business_name: v })} />
          <F id="contact-name" label="Contact person's full name" value={c.name} onChange={(v) => setC({ ...c, name: v })} />
          <F id="contact-phone" label="Telephone number" type="tel" value={c.phone} onChange={(v) => setC({ ...c, phone: v })} />
          <F id="contact-email" label="Email address" type="email" value={c.email} onChange={(v) => setC({ ...c, email: v })} />
          <F id="address" label="Full premises address" value={biz.address} onChange={(v) => setBiz({ ...biz, address: v })} />
          <F id="postcode" label="Postcode" value={biz.postcode} onChange={(v) => setBiz({ ...biz, postcode: v.toUpperCase() })} />
        </div>
      </Sec>
      <Sec title="About the premises">
        <div className="grid gap-4 sm:grid-cols-2">
          {[...COMMON, ...(EXTRA[type] || [])].map(([k, l]) => <F key={k} id={k} label={l} value={det[k]} onChange={d(k)} />)}
        </div>
        <div><Label>Current condition</Label><Pills options={CONDITION} value={det.condition} onChange={d("condition")} testid="wt-condition" /></div>
        <F id="attention" label="Areas requiring particular attention" area value={det.attention} onChange={d("attention")} />
        <F id="special" label="Any special cleaning requirements" area value={det.special} onChange={d("special")} />
      </Sec>
      <Sec title="Cleaning schedule">
        <Pills options={[["one_off", "One-off clean"], ["ongoing", "Ongoing contract"]]} value={sch.kind} onChange={(v) => setSch({ ...sch, kind: v })} testid="wt-kind" />
        {sch.kind === "ongoing" && <div><Label>How often?</Label><Pills options={FREQ} value={sch.frequency} onChange={(v) => setSch({ ...sch, frequency: v })} testid="wt-frequency" /></div>}
        <div><Label>Which days suit you?</Label><div className="mt-3 flex flex-wrap gap-2">{DAYS.map((x) => <button key={x} type="button" data-testid={`wt-day-${x}`} onClick={() => setSch({ ...sch, days: sch.days.includes(x) ? sch.days.filter((y) => y !== x) : [...sch.days, x] })}
          className={`rounded-full border px-4 py-2 text-sm ${sch.days.includes(x) ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-200"}`}>{x}</button>)}</div></div>
        <div><Label>Preferred cleaning time</Label><Pills options={TIMES} value={sch.time} onChange={(v) => setSch({ ...sch, time: v })} testid="wt-time" /></div>
        <div className="grid gap-4 sm:grid-cols-2"><F id="start" label="Ideal start date" type="date" value={sch.start_date} onChange={(v) => setSch({ ...sch, start_date: v })} /></div>
        <F id="schedule-notes" label="Anything else about scheduling" area value={sch.notes} onChange={(v) => setSch({ ...sch, notes: v })} />
      </Sec>
      <Sec title="Upload Photos of Your Premises">
        <PhotoUploader pub={pub} photos={photos} setPhotos={setPhotos} title="" text="Photographs help us understand your premises before the visit. Add photos of the main areas, washrooms, kitchens and anywhere that needs particular attention." />
      </Sec>
      <Sec title="When Would You Like Us to Visit?">
        <p className="text-sm text-slate-600">Choose a date and time that suits you. This is a request - we'll check our availability and contact you to confirm.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <F id="visit-date" label="Preferred date" type="date" value={visit.preferred_date} onChange={(v) => setVisit({ ...visit, preferred_date: v })} />
          <div><Label>Preferred time</Label><Pills options={VISIT_TIMES.map((t) => [t, t])} value={visit.preferred_time} onChange={(v) => setVisit({ ...visit, preferred_time: v })} testid="wt-visit-time" /></div>
          <F id="alt-date" label="Alternative date (optional)" type="date" value={visit.alt_date} onChange={(v) => setVisit({ ...visit, alt_date: v })} />
          <div><Label>Alternative time (optional)</Label><Pills options={VISIT_TIMES.map((t) => [t, t])} value={visit.alt_time} onChange={(v) => setVisit({ ...visit, alt_time: v })} testid="wt-alt-time" /></div>
        </div>
        <F id="access-info" label="How should we arrange access to the premises for the visit?" area value={visit.access_info} onChange={(v) => setVisit({ ...visit, access_info: v })} />
      </Sec>
      <label className="flex items-start gap-3 text-sm text-slate-600"><Checkbox checked={consent} onCheckedChange={(x) => setConsent(!!x)} data-testid="wt-consent" />I'd like occasional updates and offers by email (optional).</label>
      <Button disabled={!ok || busy} onClick={submit} className="h-14 w-full rounded-full bg-[#023F00] text-base font-bold uppercase tracking-wide text-white hover:bg-[#8F7E22] sm:w-auto sm:px-10" data-testid="wt-submit-btn">
        {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Book a free site walkthrough</Button>
      {!ok && <p className="text-xs text-slate-500">Please complete your business details, premises address and preferred visit date and time.</p>}
    </div>
  );
}
