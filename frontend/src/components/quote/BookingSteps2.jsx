import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ChoiceCard } from "@/components/quote/Controls";
import { SlotPicker } from "@/components/quote/SlotPicker";
import { AREAS, FLOORING, FURNISHED, PETS, isEot } from "@/components/quote/BookingSteps";
import { gbp } from "@/lib/api";

export const ACCESS = [["customer_present", "I will be present"], ["authorised_person", "Another authorised person will give access"], ["estate_agency", "Keys must be collected from an estate agency"], ["other", "Other arrangement"]];
export const accessOk = (a) => (a.method === "estate_agency" ? a.agency_name.trim() && a.agency_address.trim() : a.method === "authorised_person" ? a.person_name.trim() && a.person_phone.trim() : true);

const F = ({ id, label, value, onChange, area, type = "text" }) => (
  <div className={area ? "sm:col-span-2" : ""}>
    <Label htmlFor={id}>{label}</Label>
    {area ? <Textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} className="mt-2 rounded-xl" data-testid={`${id}-input`} />
      : <Input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)} className="mt-2 h-11 rounded-xl" data-testid={`${id}-input`} />}
  </div>
);

export function StepAccess({ access, setAccess }) {
  const set = (k) => (v) => setAccess({ ...access, [k]: v });
  return (
    <div className="space-y-6" data-testid="access-step">
      <div className="grid gap-3 sm:grid-cols-2">
        {ACCESS.map(([k, t]) => <ChoiceCard key={k} active={access.method === k} onClick={() => set("method")(k)} title={t} testid={`access-${k}`} />)}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {access.method === "authorised_person" && <><F id="access-person-name" label="Their name" value={access.person_name} onChange={set("person_name")} /><F id="access-person-phone" label="Their phone number" type="tel" value={access.person_phone} onChange={set("person_phone")} /></>}
        {access.method === "estate_agency" && <>
          <F id="access-agency-name" label="Estate agency name" value={access.agency_name} onChange={set("agency_name")} />
          <F id="access-agency-address" label="Estate agency address" value={access.agency_address} onChange={set("agency_address")} />
          <F id="access-agency-instructions" label="Key collection instructions (who to ask, opening hours, reference)" area value={access.agency_instructions} onChange={set("agency_instructions")} />
        </>}
        <F id="access-notes" label="Other access instructions (e.g. key safe, concierge, alarm) - optional" area value={access.notes} onChange={set("notes")} />
      </div>
      <p className="text-xs text-slate-500">Access details are kept private and only shared with the Solid Clean team assigned to your job.</p>
    </div>
  );
}

export function StepContact({ config, needsReview, date, setDate, slot, setSlot, contact, setContact, form, set, preview, postcodeOk }) {
  return (
    <div className="space-y-8" data-testid="details-step">
      {needsReview
        ? <div className="rounded-2xl bg-amber-50 p-6 text-sm text-amber-900" data-testid="quote-needs-review">This request needs a quick review by our team before we can fix a price or a time. Leave your details and we'll contact you.</div>
        : <SlotPicker availability={config.availability} date={date} setDate={setDate} slot={slot} setSlot={setSlot} />}
      <div className="grid gap-4 sm:grid-cols-2">
        {[["name", "Full name", "text"], ["phone", "Phone", "tel"], ["email", "Email", "email"]].map(([k, l, t]) => (
          <div key={k} className={k === "email" ? "sm:col-span-2" : ""}>
            <Label htmlFor={k}>{l}</Label>
            <Input id={k} type={t} value={contact[k]} onChange={(e) => setContact({ ...contact, [k]: e.target.value })} className="mt-2 h-11 rounded-xl" data-testid={`quote-contact-${k}-input`} />
          </div>
        ))}
        <div className="sm:col-span-2">
          <Label htmlFor="promo">Promo code (optional)</Label>
          <Input id="promo" value={form.promo_code} onChange={(e) => set("promo_code", e.target.value.toUpperCase())} className="mt-2 h-11 max-w-xs rounded-xl font-mono" data-testid="quote-promo-input" />
          {preview?.promo_error && form.promo_code && <p className="mt-1 text-xs text-red-600" data-testid="quote-promo-error">{preview.promo_error}</p>}
        </div>
        <div className="sm:col-span-2 mt-2 border-t border-slate-200 pt-6"><p className="eyebrow">Property address</p></div>
        <div className="sm:col-span-2"><Label htmlFor="addr">Address (house number, street, town)</Label><Input id="addr" value={form.address} onChange={(e) => set("address", e.target.value)} className="mt-2 h-11 rounded-xl" data-testid="quote-address-input" /></div>
        <div><Label htmlFor="pc">Postcode</Label><Input id="pc" value={form.postcode} onChange={(e) => set("postcode", e.target.value.toUpperCase())} placeholder="e.g. SW19 2AB" className="mt-2 h-11 rounded-xl font-mono" data-testid="quote-postcode-input" />
          {form.postcode && !postcodeOk && <p className="mt-1 text-xs text-red-600">Please enter a valid UK postcode</p>}</div>
        <label className="flex items-start gap-3 text-sm text-slate-600 sm:col-span-2">
          <Checkbox checked={contact.marketing_consent} onCheckedChange={(c) => setContact({ ...contact, marketing_consent: !!c })} data-testid="quote-marketing-consent-checkbox" />
          I'd like occasional offers and cleaning tips by email. (Optional - you can unsubscribe at any time.)
        </label>
      </div>
    </div>
  );
}

export function StepTerms({ policies, base, accepted, setAccepted, needsReview }) {
  if (!policies.length) return <p className="text-sm text-slate-500">No booking terms published.</p>;
  return (
    <div className="space-y-5" data-testid="terms-step">
      {policies.map((x) => (
        <div key={x.key} className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-display font-semibold text-slate-900">{x.title}</h3><span className="font-mono text-[11px] text-slate-500">Version {x.published_version}</span></div>
          <div className="mt-3 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-relaxed text-slate-700" data-testid={`terms-text-${x.key}`}>{x.published_content}</div>
          <a href={`${base}/policies#${x.key}`} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-medium text-[#023F00] underline">Open full policy in a new tab</a>
          {x.require_acceptance && !needsReview && (
            <label className="mt-4 flex items-start gap-3 text-sm font-medium text-slate-800">
              <Checkbox checked={!!accepted[x.key]} onCheckedChange={(c) => setAccepted({ ...accepted, [x.key]: !!c })} data-testid={`quote-accept-${x.key}`} />
              I have read and accept the {x.title} (version {x.published_version}).
            </label>
          )}
        </div>
      ))}
    </div>
  );
}

const Row = ({ k, v }) => (v ? <div className="flex justify-between gap-4 border-b border-slate-100 py-2 text-sm"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium text-slate-900">{v}</dd></div> : null);
const name = (list, key) => list.find(([k]) => k === key)?.[1];

const TIPS = [0, 5, 10, 15];

function TipPicker({ tip, setTip }) {
  const [other, setOther] = useState(false);
  const pill = (on) => `rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${on ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-300 bg-white text-slate-700 hover:border-[#8F7E22]"}`;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="tip-picker">
      <h3 className="font-display font-semibold text-slate-900">Add a tip for your cleaning team</h3>
      <p className="mt-1 text-xs text-slate-500">Optional - added to your card payment.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {TIPS.map((t) => <button key={t} type="button" className={pill(!other && tip === t)} onClick={() => { setOther(false); setTip(t); }} data-testid={`tip-option-${t}`}>{t ? gbp(t) : "No tip"}</button>)}
        <button type="button" className={pill(other)} onClick={() => setOther(true)} data-testid="tip-option-other">Other</button>
      </div>
      {other && <Input type="number" min="0" max="500" step="1" placeholder="Amount in £" value={tip || ""} onChange={(e) => setTip(Math.min(500, Math.max(0, Number(e.target.value) || 0)))} className="mt-3 w-40 font-mono" data-testid="tip-custom-input" />}
    </div>
  );
}

const PayConfirm = ({ base, payOk, setPayOk }) => (
  <label className="flex items-start gap-3 rounded-2xl border-2 border-[#023F00]/30 bg-[#023F00]/5 p-4 text-sm font-medium text-slate-800" data-testid="pay-terms-confirm">
    <Checkbox checked={payOk} onCheckedChange={(c) => setPayOk(!!c)} className="mt-0.5" data-testid="quote-pay-terms-checkbox" />
    <span>I have read and accept the <a href={`${base}/terms`} target="_blank" rel="noreferrer" className="font-semibold text-[#023F00] underline" data-testid="pay-terms-link">Terms and Conditions</a>, including the cancellation and refund policy.</span>
  </label>
);

export function StepReview({ p, svc, form, access, photos, date, slot, contact, preview, policies, needsReview, deposit, tip, setTip, payOk, setPayOk, base }) {
  const ptype = p.property_types.find((t) => t.key === form.property_type)?.name;
  const cond = p.conditions.find((c) => c.key === form.condition)?.name;
  return (
    <div className="space-y-6" data-testid="review-step">
      <dl className="rounded-2xl border border-slate-200 bg-white p-5">
        <Row k="Service" v={svc?.name} />
        <Row k="Property" v={`${ptype} · ${form.bedrooms} bed · ${form.bathrooms} bath · ${form.living_rooms} living`} />
        <Row k="Address" v={`${form.address}, ${form.postcode}`} />
        <Row k="Condition" v={cond} />
        {isEot(form.service) && <Row k="Furnished" v={name(FURNISHED, form.furnished)} />}
        {isEot(form.service) && <Row k="Flooring" v={name(FLOORING, form.flooring)} />}
        <Row k="Pets" v={`${name(PETS, form.pets) || "-"}${form.pet_hair_odour ? " · significant pet hair/odour" : ""}`} />
        <Row k="Additional areas (noted for our team)" v={form.additional_areas.filter((a) => AREAS.includes(a)).join(", ")} />
        <Row k="Photos" v={`${photos.filter((x) => x.status === "done").length} uploaded`} />
        <Row k="Access" v={name(ACCESS, access.method) + (access.method === "estate_agency" ? ` - ${access.agency_name}` : access.method === "authorised_person" ? ` - ${access.person_name}` : "")} />
        {!needsReview && <Row k="Appointment" v={date ? `${date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })} · ${slot}` : ""} />}
        <Row k="Your details" v={`${contact.name} · ${contact.phone} · ${contact.email}`} />
      </dl>
      {!needsReview && preview?.lines && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="review-price-breakdown">
          <h3 className="eyebrow">Itemised price</h3>
          <ul className="mt-3 space-y-1.5 text-sm">{preview.lines.map((l) => <li key={l.label} className="flex justify-between"><span>{l.label}</span><span className="font-mono">{gbp(l.amount)}</span></li>)}</ul>
          <div className="mt-3 flex justify-between border-t border-dashed pt-3 font-semibold"><span>Total</span><span className="font-mono" data-testid="review-total">{gbp(preview.total)}</span></div>
          {tip > 0 && <>
            <div className="mt-1 flex justify-between text-sm text-slate-600"><span>Tip for your cleaning team</span><span className="font-mono" data-testid="review-tip">{gbp(tip)}</span></div>
            <div className="flex justify-between font-semibold text-[#023F00]"><span>To pay now</span><span className="font-mono" data-testid="review-pay-now">{gbp(deposit + tip)}</span></div>
          </>}
          {deposit < preview.total && <>
            <div className="mt-1 flex justify-between text-sm text-[#023F00]"><span>50% deposit to pay now</span><span className="font-mono" data-testid="review-deposit">{gbp(deposit)}</span></div>
            <div className="flex justify-between text-sm text-slate-600"><span>Balance due immediately after the clean</span><span className="font-mono">{gbp(preview.total - deposit)}</span></div>
          </>}
          <p className="mt-3 text-xs text-slate-500">Card payments only, processed securely by Stripe. Your booking is confirmed once the {deposit < preview.total ? "deposit" : "payment"} is received.</p>
        </div>
      )}
      {!needsReview && preview?.lines && <TipPicker tip={tip} setTip={setTip} />}
      {!needsReview && preview?.lines && <PayConfirm base={base} payOk={payOk} setPayOk={setPayOk} />}
      {needsReview && <p className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">{(preview?.reasons || []).join(" ")} We'll review your details and photos and contact you with an exact price - nothing is charged now.</p>}
      <p className="text-xs text-slate-500">Booking terms: {policies.map((x) => `${x.title} (v${x.published_version})`).join(", ") || "-"}</p>
    </div>
  );
}
