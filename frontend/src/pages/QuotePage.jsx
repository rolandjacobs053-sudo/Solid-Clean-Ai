import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { format } from "date-fns";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg, gbp, getSource } from "@/lib/api";
import { useTenant } from "@/lib/tenant";
import { ChoiceCard, Counter } from "@/components/quote/Controls";
import { QuoteSummary } from "@/components/quote/QuoteSummary";
import { SlotPicker } from "@/components/quote/SlotPicker";

const STEPS = ["Property", "Rooms & extras", "Date & time", "Your details"];
const INITIAL = { service: "regular", property_type: "flat", bedrooms: 2, bathrooms: 1, living_rooms: 1, condition: "good", extras: [], parking: "free", postcode: "" };

export default function QuotePage() {
  const { base, pub } = useTenant();
  const [params] = useSearchParams();
  const [config, setConfig] = useState(null);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(INITIAL);
  const [quoteId, setQuoteId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [date, setDate] = useState();
  const [slot, setSlot] = useState("");
  const [contact, setContact] = useState({ name: "", email: "", phone: "", marketing_consent: false });
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    api.get(`${pub}/config`).then((r) => setConfig(r.data));
    const q = params.get("q");
    if (q) api.get(`${pub}/quotes/${q}`).then((r) => { setForm({ ...INITIAL, ...r.data.input }); setQuoteId(q); setStep(2); }).catch(() => {});
  }, [params, pub]);

  useEffect(() => {
    const t = setTimeout(() => api.post(`${pub}/quote/preview`, form).then((r) => setPreview(r.data)).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [form, pub]);

  if (!config) return <div className="p-16 text-center font-mono text-sm text-slate-500">Loading price list…</div>;
  const p = config.pricing;
  const needsReview = preview?.status === "needs_review";
  const postcodeOk = /^[A-Za-z]{1,2}\d/.test(form.postcode.trim());
  const canNext = [postcodeOk, true, needsReview || (date && slot), true][step];
  const contactOk = contact.name && /\S+@\S+\.\S+/.test(contact.email) && contact.phone.length >= 6;

  const submit = async (mode) => {
    if (!contactOk) return toast.error("Please add your name, a valid email and phone number.");
    setBusy(true);
    try {
      if (mode === "book") {
        const { data } = await api.post(`${pub}/bookings`, { quote: form, contact, date: format(date, "yyyy-MM-dd"), slot, access_notes: notes, source: getSource(), quote_id: quoteId, origin_url: `${window.location.origin}${base}` });
        if (data.confirmed) {
          toast.success(`Booking confirmed. ${data.payment_instructions || ""}`, { duration: 10000 });
          setBusy(false);
          setStep(0);
          return;
        }
        window.location.href = data.checkout_url;
        return;
      }
      await api.post(`${pub}/quotes`, { quote: form, contact, source: getSource() });
      toast.success(needsReview ? "Thanks - our team will review and contact you shortly." : "Quote sent to your email.");
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8" data-testid="quote-page">
      <p className="eyebrow">Instant quote &amp; booking</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">Your clean, priced precisely.</h1>
      <ol className="mt-8 flex flex-wrap gap-2" data-testid="quote-stepper">
        {STEPS.map((s, i) => (
          <li key={s} className={`rounded-full px-4 py-1.5 font-mono text-xs ${i === step ? "bg-slate-900 text-white" : i < step ? "bg-teal-100 text-teal-800" : "bg-slate-100 text-slate-500"}`}>0{i + 1} {s}</li>
        ))}
      </ol>
      <div className="mt-10 grid gap-10 lg:grid-cols-12">
        <section className="space-y-8 lg:col-span-7">
          {step === 0 && (
            <>
              <div>
                <Label className="eyebrow">Service</Label>
                <div className="mt-3 grid gap-3 sm:grid-cols-2" data-testid="quote-service-options">
                  {p.services.map((s) => <ChoiceCard key={s.key} active={form.service === s.key} onClick={() => set("service", s.key)} title={s.name} sub={s.requires_survey ? "Priced after a short survey" : `From ${gbp(s.min_price)}`} testid={`quote-service-${s.key}`} />)}
                </div>
              </div>
              <div>
                <Label className="eyebrow">Property type</Label>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="quote-property-type-select">
                  {p.property_types.map((t) => <ChoiceCard key={t.key} active={form.property_type === t.key} onClick={() => set("property_type", t.key)} title={t.name} testid={`quote-ptype-${t.key}`} />)}
                </div>
              </div>
              <div className="max-w-xs">
                <Label htmlFor="pc" className="eyebrow">Property postcode</Label>
                <Input id="pc" value={form.postcode} onChange={(e) => set("postcode", e.target.value.toUpperCase())} placeholder="e.g. SW19 2AB" className="mt-3 h-12 rounded-xl font-mono" data-testid="quote-postcode-input" />
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <div className="grid gap-3">
                <Counter label="Bedrooms" value={form.bedrooms} onChange={(v) => set("bedrooms", v)} max={12} testid="quote-bedrooms-count" />
                <Counter label="Bathrooms" value={form.bathrooms} onChange={(v) => set("bathrooms", v)} testid="quote-bathrooms-count" />
                <Counter label="Living rooms" value={form.living_rooms} onChange={(v) => set("living_rooms", v)} max={6} testid="quote-living-count" />
              </div>
              <div>
                <Label className="eyebrow">Condition</Label>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {p.conditions.map((c) => <ChoiceCard key={c.key} active={form.condition === c.key} onClick={() => set("condition", c.key)} title={c.name} testid={`quote-condition-${c.key}`} />)}
                </div>
              </div>
              <div>
                <Label className="eyebrow">Extras</Label>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {p.extras.map((x) => (
                    <label key={x.key} className="flex cursor-pointer items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm hover:border-teal-300">
                      <span className="flex items-center gap-3">
                        <Checkbox checked={form.extras.includes(x.key)} data-testid={`quote-extra-${x.key}`}
                          onCheckedChange={(c) => set("extras", c ? [...form.extras, x.key] : form.extras.filter((k) => k !== x.key))} />{x.name}
                      </span>
                      <span className="font-mono text-xs text-slate-500">+{gbp(x.price)}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <Label className="eyebrow">Parking</Label>
                <div className="mt-3 grid grid-cols-3 gap-3">
                  {[["free", "Free parking"], ["paid", "Paid / permit"], ["none", "No parking nearby"]].map(([k, t]) => (
                    <ChoiceCard key={k} active={form.parking === k} onClick={() => set("parking", k)} title={t} testid={`quote-parking-${k}`} />
                  ))}
                </div>
              </div>
            </>
          )}
          {step === 2 && (needsReview
            ? <div className="rounded-2xl bg-amber-50 p-6 text-sm text-amber-900" data-testid="quote-needs-review">This request needs a quick review by our team before we can fix a price or a time. Continue to leave your details and we'll call you.</div>
            : <SlotPicker availability={config.availability} date={date} setDate={setDate} slot={slot} setSlot={setSlot} />)}
          {step === 3 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {[["name", "Full name", "text"], ["phone", "Phone", "tel"], ["email", "Email", "email"]].map(([k, l, t]) => (
                <div key={k} className={k === "email" ? "sm:col-span-2" : ""}>
                  <Label htmlFor={k}>{l}</Label>
                  <Input id={k} type={t} value={contact[k]} onChange={(e) => setContact({ ...contact, [k]: e.target.value })} className="mt-2 h-11 rounded-xl" data-testid={`quote-contact-${k}-input`} />
                </div>
              ))}
              <div className="sm:col-span-2">
                <Label htmlFor="notes">Access, keys, pets or special requests</Label>
                <Textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-2 rounded-xl" data-testid="quote-access-notes-input" />
              </div>
              <label className="flex items-start gap-3 text-sm text-slate-600 sm:col-span-2">
                <Checkbox checked={contact.marketing_consent} onCheckedChange={(c) => setContact({ ...contact, marketing_consent: !!c })} data-testid="quote-marketing-consent-checkbox" />
                I'd like occasional offers and cleaning tips by email. (Optional - you can unsubscribe at any time.)
              </label>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-6">
            {step > 0 && <Button variant="ghost" onClick={() => setStep(step - 1)} data-testid="quote-back-btn"><ArrowLeft className="mr-1 h-4 w-4" />Back</Button>}
            {step < 3 && <Button disabled={!canNext} onClick={() => setStep(step + 1)} className="rounded-full bg-slate-900 px-7 hover:bg-teal-700 hover:text-white" data-testid="quote-next-btn">Continue<ArrowRight className="ml-1 h-4 w-4" /></Button>}
            {step === 3 && !needsReview && (
              <Button disabled={busy} onClick={() => submit("book")} className="rounded-full bg-teal-600 px-7 hover:bg-teal-700 hover:text-white" data-testid="quote-book-now-btn">
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Pay {gbp(preview?.total)} &amp; confirm
              </Button>
            )}
            {step === 3 && (
              <Button variant="outline" disabled={busy} onClick={() => submit("quote")} className="rounded-full" data-testid="quote-email-quote-btn">
                {needsReview ? "Send enquiry" : "Just email me this quote"}
              </Button>
            )}
            {step === 0 && !postcodeOk && <span className="text-xs text-slate-500">Enter a valid postcode to continue</span>}
          </div>
        </section>
        <div className="lg:col-span-5"><QuoteSummary preview={preview} form={form} date={!needsReview && date} slot={slot} config={config} /></div>
      </div>
    </main>
  );
}
