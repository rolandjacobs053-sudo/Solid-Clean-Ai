import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { format } from "date-fns";
import { CheckCircle2, Loader2, Repeat } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ChoiceCard, Counter } from "@/components/quote/Controls";
import { Pills, StepExtras } from "@/components/quote/BookingSteps";
import { ACCESS, PayConfirm, StepAccess, StepTerms, TipPicker, accessOk } from "@/components/quote/BookingSteps2";
import { BookingShell, StepNav } from "@/components/quote/BookingShell";
import { PhotoUploader } from "@/components/quote/PhotoUploader";
import { QuoteSummary } from "@/components/quote/QuoteSummary";
import { SlotPicker } from "@/components/quote/SlotPicker";
import { api, errMsg, gbp, getSource } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

const STEPS = ["Frequency", "Property", "Services", "Date & time", "Your details", "Address", "Photos", "Review & pay"];
const TITLES = ["How often would you like us to clean?", "Tell us about your home", "What cleaning services do you need?", "Choose a date and time", "Your contact details", "Property address & access", "Photos of your property (optional)", "Review and confirm"];
const INITIAL = { service: "regular", frequency: "", property_type: "flat", bedrooms: 2, bathrooms: 1, living_rooms: 1, condition: "good", people: "", pets: "", last_cleaned: "",
  tasks: ["general", "kitchen", "bathroom", "dusting", "mopping"], task_qty: {}, other_request: "", extras: [], extra_qty: {}, postcode: "", address: "", promo_code: "" };
const ACCESS0 = { method: "customer_present", person_name: "", person_phone: "", agency_name: "", agency_address: "", agency_instructions: "", notes: "" };
const opts = (rows) => rows.map((r) => [r.key, r.name]);
const Q = ({ l, children }) => <div><Label className="text-sm font-semibold text-slate-900">{l}</Label>{children}</div>;

function Tasks({ res, form, set }) {
  const toggle = (k) => set("tasks", form.tasks.includes(k) ? form.tasks.filter((x) => x !== k) : [...form.tasks, k]);
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="res-tasks">
      {res.tasks.map((t) => {
        const on = form.tasks.includes(t.key), n = form.task_qty[t.key] || 1;
        return (
          <div key={t.key} className={`rounded-2xl border bg-white p-4 text-sm transition-colors ${on ? "border-[#023F00] ring-1 ring-[#023F00]" : "border-slate-200"}`}>
            <label className="flex cursor-pointer items-start justify-between gap-3">
              <span className="flex items-start gap-3"><Checkbox checked={on} onCheckedChange={() => toggle(t.key)} className="mt-0.5" data-testid={`res-task-${t.key}`} /><span className="font-medium text-slate-900">{t.name}</span></span>
              <span className="whitespace-nowrap text-right font-mono text-xs text-slate-600">{t.price ? `+${gbp(t.price * (t.per_item && on ? n : 1))}` : "Included"}{t.per_item && t.price > 0 && <span className="block text-[11px] text-slate-500">{gbp(t.price)} per {t.unit}</span>}</span>
            </label>
            {on && t.per_item && <div className="mt-3 pl-7"><Counter label={`Number of ${t.unit}s`} value={n} onChange={(v) => set("task_qty", { ...form.task_qty, [t.key]: v })} min={1} max={t.max_qty || 10} testid={`res-task-qty-${t.key}`} /></div>}
            {on && t.key === "other" && <Textarea className="mt-3 rounded-xl" placeholder="Tell us what else you need - we'll confirm any extra cost before the clean" value={form.other_request} onChange={(e) => set("other_request", e.target.value)} data-testid="res-other-request" />}
          </div>
        );
      })}
    </div>
  );
}

function Review({ res, p, form, date, slot, contact, access, photos, preview }) {
  const f = (rows, k) => rows.find((r) => r.key === k)?.name;
  const tasks = res.tasks.filter((t) => form.tasks.includes(t.key)).map((t) => t.name + (t.per_item ? ` × ${form.task_qty[t.key] || 1}` : "")).join(", ");
  const rows = [["Frequency", f(res.frequencies, form.frequency)], ["Property", `${f(p.property_types, form.property_type)} · ${form.bedrooms} bed · ${form.bathrooms} bath`], ["People", f(res.people, form.people)],
    ["Pets", form.pets === "yes" ? "Yes" : "No"], ["Last cleaned", f(res.last_cleaned, form.last_cleaned)], ["Services", tasks], ["Other requests", form.other_request],
    ["Add-ons", p.extras.filter((x) => form.extras.includes(x.key)).map((x) => x.name + (x.per_item ? ` × ${form.extra_qty[x.key] || 1}` : "")).join(", ")],
    ["Appointment", date ? `${date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })} · ${slot}` : ""], ["Your details", `${contact.name} · ${contact.phone} · ${contact.email}`],
    ["Address", `${form.address}, ${form.postcode}`], ["Access", ACCESS.find(([k]) => k === access.method)?.[1]], ["Photos", `${photos.filter((x) => x.status === "done").length} uploaded`]];
  return (
    <div className="space-y-6" data-testid="res-review">
      <dl className="rounded-2xl border border-slate-200 bg-white p-5">{rows.filter(([, v]) => v).map(([k, v]) => <div key={k} className="flex justify-between gap-4 border-b border-slate-100 py-2 text-sm"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium text-slate-900">{v}</dd></div>)}</dl>
      {preview?.lines && <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="res-price-breakdown">
        <h3 className="eyebrow">Price {form.frequency !== "one_off" ? "per visit" : ""}</h3>
        <ul className="mt-3 space-y-1.5 text-sm">{preview.lines.map((l) => <li key={l.label} className="flex justify-between gap-3"><span>{l.label}</span><span className="font-mono">{gbp(l.amount)}</span></li>)}</ul>
        <div className="mt-3 flex justify-between border-t border-dashed pt-3 text-lg font-bold text-[#023F00]"><span>Total</span><span className="font-mono" data-testid="res-total">{gbp(preview.total)}</span></div>
      </div>}
    </div>
  );
}

export default function ResidentialBooking() {
  const cfg = useOutletContext();
  const pub = `/public/${DEFAULT_SLUG}`;
  const [config, setConfig] = useState(null);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(INITIAL);
  const [preview, setPreview] = useState(null);
  const [date, setDate] = useState();
  const [slot, setSlot] = useState("");
  const [contact, setContact] = useState({ name: "", email: "", phone: "", marketing_consent: false });
  const [access, setAccess] = useState(ACCESS0);
  const [photos, setPhotos] = useState([]);
  const [accepted, setAccepted] = useState({});
  const [tip, setTip] = useState(0);
  const [payOk, setPayOk] = useState(false);
  const [autoOk, setAutoOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  useEffect(() => { api.get(`${pub}/config`).then((r) => setConfig(r.data)); }, [pub]);
  useEffect(() => {
    if (!form.frequency) return undefined;
    const t = setTimeout(() => api.post(`${pub}/quote/preview`, { ...form, date: date ? format(date, "yyyy-MM-dd") : "" }).then((r) => setPreview(r.data)).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [form, pub, date]);
  if (!config) return <div className="p-16 text-center font-mono text-sm text-slate-500">Loading…</div>;
  const p = config.pricing, res = p.residential;
  const svc = p.services.find((s) => s.key === "regular");
  const policies = config.policies || [];
  const required = policies.filter((x) => x.require_acceptance);
  const recurring = ["weekly", "fortnightly", "monthly"].includes(form.frequency);
  const uploading = photos.some((x) => x.status === "uploading");
  const okStep = [!!form.frequency, !!form.people && !!form.pets && !!form.last_cleaned, form.tasks.length > 0 && (!form.tasks.includes("other") || form.other_request.trim()), !!date && !!slot,
    contact.name && /\S+@\S+\.\S+/.test(contact.email) && contact.phone.length >= 6, form.address.trim().length >= 5 && /^[A-Za-z]{1,2}\d/.test(form.postcode.trim()) && accessOk(access), !uploading, true][step];
  const hints = ["Choose how often", "Answer the people, pets and last-cleaned questions", "Choose at least one service (describe 'Other' requests)", "Choose a date and time", "Add your full name, phone and email", "Add the full address, a valid postcode and access details", "Please wait for photos to finish uploading", ""];
  const payReady = preview?.status === "ok" && required.every((x) => accepted[x.key]) && payOk && (!recurring || autoOk);
  const pay = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`${pub}/bookings`, { quote: form, contact, date: format(date, "yyyy-MM-dd"), slot, access, source: getSource(),
        photos: photos.filter((x) => x.status === "done").map(({ id, token }) => ({ id, token })), accepted_policies: Object.fromEntries(required.map((x) => [x.key, x.published_version])),
        pay_terms_accepted: payOk, auto_charge_consent: autoOk, tip, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  return (
    <BookingShell prefix="res" eyebrow="Residential cleaning · book online" title={TITLES[step]} steps={STEPS} step={step} phone={cfg.business.phone}
      aside={<QuoteSummary preview={form.frequency ? preview : null} form={form} date={date} slot={slot} config={config} />}>
      {step === 0 && <div className="grid gap-3 sm:grid-cols-2" data-testid="res-frequency">{res.frequencies.map((x) => <ChoiceCard key={x.key} active={form.frequency === x.key} onClick={() => set("frequency", x.key)} title={x.name} sub={x.discount ? `Save ${x.discount}% on every visit` : "A single clean, no commitment"} testid={`res-frequency-${x.key}`} />)}</div>}
      {step === 1 && <div className="space-y-7" data-testid="res-property">
        <Q l="What type of property do you have?"><Pills options={opts(p.property_types)} value={form.property_type} onChange={(v) => set("property_type", v)} testid="res-property-type" /></Q>
        <div className="grid gap-4 sm:grid-cols-2"><Counter label="Bedrooms" value={form.bedrooms} onChange={(v) => set("bedrooms", v)} min={0} max={12} testid="res-bedrooms" /><Counter label="Bathrooms" value={form.bathrooms} onChange={(v) => set("bathrooms", v)} min={1} max={10} testid="res-bathrooms" /></div>
        <Q l="How many people live in the property?"><Pills options={opts(res.people)} value={form.people} onChange={(v) => set("people", v)} testid="res-people" /></Q>
        <Q l="Do you have pets?"><Pills options={[["yes", "Yes"], ["no", "No"]]} value={form.pets} onChange={(v) => set("pets", v)} testid="res-pets" /></Q>
        <Q l="When was the property last cleaned?"><Pills options={opts(res.last_cleaned)} value={form.last_cleaned} onChange={(v) => set("last_cleaned", v)} testid="res-last-cleaned" /></Q>
      </div>}
      {step === 2 && <div className="space-y-8"><Tasks res={res} form={form} set={set} />
        <div><h3 className="eyebrow mb-3">Optional add-ons</h3><StepExtras p={p} svc={svc} form={form} set={set} preview={preview} /></div></div>}
      {step === 3 && <SlotPicker availability={config.availability} date={date} setDate={setDate} slot={slot} setSlot={setSlot} />}
      {step === 4 && <div className="grid gap-4 sm:grid-cols-2" data-testid="res-contact">
        {[["name", "Full name", "text"], ["phone", "Phone number", "tel"], ["email", "Email address", "email"]].map(([k, l, t]) => <div key={k} className={k === "name" ? "sm:col-span-2" : ""}><Label htmlFor={k}>{l}</Label><Input id={k} type={t} value={contact[k]} onChange={(e) => setContact({ ...contact, [k]: e.target.value })} className="mt-2 h-11 rounded-xl" data-testid={`res-contact-${k}`} /></div>)}
        <div className="sm:col-span-2"><Label htmlFor="promo">Promo code (optional)</Label><Input id="promo" value={form.promo_code} onChange={(e) => set("promo_code", e.target.value.toUpperCase())} className="mt-2 h-11 max-w-xs rounded-xl font-mono" data-testid="res-promo" /></div>
        <label className="flex items-start gap-3 text-sm text-slate-600 sm:col-span-2"><Checkbox checked={contact.marketing_consent} onCheckedChange={(c) => setContact({ ...contact, marketing_consent: !!c })} />I'd like occasional offers and cleaning tips by email (optional).</label>
      </div>}
      {step === 5 && <div className="space-y-8" data-testid="res-address">
        <div className="grid gap-4 sm:grid-cols-3"><div><Label htmlFor="pc">Postcode</Label><Input id="pc" value={form.postcode} onChange={(e) => set("postcode", e.target.value.toUpperCase())} placeholder="e.g. SW19 2AB" className="mt-2 h-11 rounded-xl font-mono" data-testid="res-postcode" /></div>
          <div className="sm:col-span-2"><Label htmlFor="addr">Full property address</Label><Input id="addr" value={form.address} onChange={(e) => set("address", e.target.value)} className="mt-2 h-11 rounded-xl" data-testid="res-address-input" /></div></div>
        <div><h3 className="eyebrow mb-3">How will we get in?</h3><StepAccess access={access} setAccess={setAccess} /></div>
      </div>}
      {step === 6 && <div data-testid="res-photos"><PhotoUploader pub={pub} photos={photos} setPhotos={setPhotos} title="" text="Optional: photos help us understand your home and any areas that need extra attention." /></div>}
      {step === 7 && <div className="space-y-6">
        <Review res={res} p={p} form={form} date={date} slot={slot} contact={contact} access={access} photos={photos} preview={preview} />
        {preview?.status !== "ok" && <p className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900" data-testid="res-needs-review">{(preview?.reasons || []).join(" ")} Please call us to book.</p>}
        <StepTerms policies={policies} base="" accepted={accepted} setAccepted={setAccepted} />
        <TipPicker tip={tip} setTip={setTip} />
        {recurring && <label className="flex items-start gap-3 rounded-2xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-4 text-sm text-slate-800" data-testid="res-auto-charge">
          <Checkbox checked={autoOk} onCheckedChange={(c) => setAutoOk(!!c)} className="mt-0.5" data-testid="res-auto-charge-checkbox" />
          <span><Repeat className="mr-1 inline h-4 w-4 text-[#023F00]" />You pay for your first clean now. I authorise Solid Clean Ltd to save my card and charge {gbp(preview?.total || 0)} automatically 2 days before each {form.frequency} visit until I cancel. I can cancel or pause at any time by contacting Solid Clean Ltd.</span>
        </label>}
        <PayConfirm base="" payOk={payOk} setPayOk={setPayOk} />
      </div>}
      <StepNav prefix="res" step={step} last={7} setStep={setStep} canNext={okStep} hint={hints[step]} nextLabel={step === 6 && !photos.length ? "Skip photos" : "Continue"}>
        {step === 7 && <Button disabled={busy || !payReady} onClick={pay} className="h-12 rounded-full bg-[#023F00] px-8 font-bold text-white hover:bg-[#8F7E22]" data-testid="res-pay-btn">
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}Pay {gbp((preview?.total || 0) + tip)} & confirm</Button>}
      </StepNav>
    </BookingShell>
  );
}
