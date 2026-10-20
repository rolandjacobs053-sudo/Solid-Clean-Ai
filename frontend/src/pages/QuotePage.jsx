import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg, gbp, getSource } from "@/lib/api";
import { useTenant } from "@/lib/tenant";
import { BookingShell, StepNav } from "@/components/quote/BookingShell";
import { QuoteSummary } from "@/components/quote/QuoteSummary";
import { PhotoUploader } from "@/components/quote/PhotoUploader";
import { StepExtras, StepProperty, StepService } from "@/components/quote/BookingSteps";
import { StepAccess, StepContact, StepReview, StepTerms, accessOk } from "@/components/quote/BookingSteps2";

const STEPS = ["Service", "Property", "Photos", "Extras", "Access", "Date & details", "Terms", "Review"];
const TITLES = ["Which cleaning service do you need?", "Tell us about the property", "Show us the property", "Any additional services?", "How will we access the property?", "Choose a time, your details & address", "Booking terms & policies", "Check your booking"];
const INITIAL = { service: "regular", property_type: "flat", bedrooms: 2, bathrooms: 1, living_rooms: 1, condition: "good", extras: [], postcode: "", promo_code: "",
  address: "", furnished: "", pets: "no", pet_hair_odour: false, additional_areas: [], flooring: "", property_notes: "" };
const ACCESS0 = { method: "customer_present", person_name: "", person_phone: "", agency_name: "", agency_address: "", agency_instructions: "", notes: "" };

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
  const [access, setAccess] = useState(ACCESS0);
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState({});
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    api.get(`${pub}/config`).then((r) => setConfig(r.data));
    const q = params.get("q");
    if (q) api.get(`${pub}/quotes/${q}`).then((r) => { setForm({ ...INITIAL, ...r.data.input }); setQuoteId(q); setStep(1); }).catch(() => {});
  }, [params, pub]);

  useEffect(() => {
    const body = { ...form, date: date ? format(date, "yyyy-MM-dd") : "" };
    const t = setTimeout(() => api.post(`${pub}/quote/preview`, body).then((r) => setPreview(r.data)).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [form, pub, date]);


  if (!config) return <div className="p-16 text-center font-mono text-sm text-slate-500">Loading price list…</div>;
  const p = { ...config.pricing, services: config.pricing.services.filter((s) => s.active !== false && s.online_booking !== false) };
  const svc = p.services.find((s) => s.key === form.service);
  const policies = config.policies || [];
  const required = policies.filter((x) => x.require_acceptance);
  const termsOk = required.every((x) => accepted[x.key]);
  const needsReview = preview?.status === "needs_review";
  const postcodeOk = /^[A-Za-z]{1,2}\d/.test(form.postcode.trim());
  const contactOk = contact.name && /\S+@\S+\.\S+/.test(contact.email) && contact.phone.length >= 6;
  const uploading = photos.some((x) => x.status === "uploading");
  const canNext = [true, true, !uploading, true, accessOk(access), contactOk && postcodeOk && form.address.trim().length >= 5 && (needsReview || (date && slot)), needsReview || termsOk, true][step];
  const hints = ["", "", "Please wait for photos to finish uploading", "", "Please complete the access details", "Choose a date & time, add your name, email, phone and the property address and postcode", "Please read and accept the booking terms", ""];
  const deposit = preview?.deposit ?? preview?.total;
  const photoRefs = photos.filter((x) => x.status === "done").map(({ id, token }) => ({ id, token }));

  const submit = async (mode) => {
    setBusy(true);
    try {
      if (mode === "book") {
        const accepted_policies = Object.fromEntries(required.map((x) => [x.key, x.published_version]));
        const { data } = await api.post(`${pub}/bookings`, { quote: form, contact, date: format(date, "yyyy-MM-dd"), slot, access, photos: photoRefs, source: getSource(), quote_id: quoteId, accepted_policies, origin_url: `${window.location.origin}${base}` });
        if (data.confirmed) { toast.success(`Booking confirmed. ${data.payment_instructions || ""}`, { duration: 10000 }); setBusy(false); setStep(0); return; }
        window.location.href = data.checkout_url;
        return;
      }
      await api.post(`${pub}/quotes`, { quote: form, contact, photos: photoRefs, source: getSource() });
      toast.success(needsReview ? "Thanks - our team will review your details and contact you shortly." : "Quote sent to your email.");
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <BookingShell prefix="quote" eyebrow="Book online" title={TITLES[step]} steps={STEPS} step={step} phone={config.business.phone}
      aside={<QuoteSummary preview={preview} form={form} date={!needsReview && date} slot={slot} config={config} />}>
          {step === 0 && <StepService services={p.services} form={form} set={(k, v) => setForm((f) => ({ ...f, [k]: v, extras: [] }))} />}
          {step === 1 && <StepProperty p={p} form={form} set={set} />}
          {step === 2 && <PhotoUploader pub={pub} photos={photos} setPhotos={setPhotos} />}
          {step === 3 && <StepExtras p={p} svc={svc} form={form} set={set} />}
          {step === 4 && <StepAccess access={access} setAccess={setAccess} />}
          {step === 5 && <StepContact config={config} needsReview={needsReview} date={date} setDate={setDate} slot={slot} setSlot={setSlot} contact={contact} setContact={setContact} form={form} set={set} preview={preview} postcodeOk={postcodeOk} />}
          {step === 6 && <StepTerms policies={policies} base={base} accepted={accepted} setAccepted={setAccepted} needsReview={needsReview} />}
          {step === 7 && <StepReview p={p} svc={svc} form={form} access={access} photos={photos} date={date} slot={slot} contact={contact} preview={preview} policies={policies} needsReview={needsReview} deposit={deposit} />}
          <StepNav prefix="quote" step={step} last={7} setStep={setStep} canNext={canNext} hint={hints[step]} nextLabel={step === 2 && !photos.length ? "Skip photos" : "Continue"}>
            {step === 7 && !needsReview && (
              <Button disabled={busy || !termsOk} onClick={() => submit("book")} className="rounded-full bg-[#023F00] px-7 text-white hover:bg-[#8F7E22]" data-testid="quote-book-now-btn">
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{deposit < preview?.total ? `Pay ${gbp(deposit)} deposit & confirm` : `Pay ${gbp(preview?.total)} & confirm`}
              </Button>
            )}
            {step === 7 && <Button variant="outline" disabled={busy || !contactOk} onClick={() => submit("quote")} className="rounded-full" data-testid="quote-email-quote-btn">{needsReview ? "Send enquiry" : "Just email me this quote"}</Button>}
          </StepNav>
    </BookingShell>
  );
}
