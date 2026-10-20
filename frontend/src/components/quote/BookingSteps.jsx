import { Link } from "react-router-dom";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ChoiceCard, Counter } from "@/components/quote/Controls";
import { gbp } from "@/lib/api";

export const AREAS = ["Conservatory", "Utility room", "Home office / study", "Loft room", "Garage", "Garden room / annex"];
export const PETS = [["no", "No pets"], ["yes", "Pets live here"], ["recent", "Pets lived here recently"]];
export const FURNISHED = [["furnished", "Furnished"], ["part", "Part furnished"], ["unfurnished", "Unfurnished"]];
export const FLOORING = [["carpet", "Mostly carpet"], ["hard", "Mostly hard floors"], ["mixed", "A mix of both"]];
export const isEot = (service) => service === "end_of_tenancy";

export function Pills({ options, value, onChange, testid }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2" data-testid={testid}>
      {options.map(([k, t]) => (
        <button key={k} type="button" onClick={() => onChange(k)} data-testid={`${testid}-${k}`}
          className={`rounded-full border px-4 py-2 text-sm transition-colors ${value === k ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-200 bg-white text-slate-700 hover:border-[#8F7E22]"}`}>{t}</button>
      ))}
    </div>
  );
}

export function StepService({ services, form, set }) {
  return (
    <>
    {form.service === "commercial" && <Link to="/commercial-cleaning/request" className="block rounded-2xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-4 text-sm font-semibold text-[#023F00]" data-testid="quote-commercial-walkthrough-link">Commercial premises are priced after a free, no-obligation site walkthrough. Book a free site walkthrough →</Link>}
    {form.service === "carpet" && <Link to="/carpet-cleaning/request" className="block rounded-2xl border-2 border-[#8F7E22] bg-[#fbf9f1] p-4 text-sm font-semibold text-[#023F00]" data-testid="quote-carpet-request-link">Carpet cleaning starts from £100 and is quoted after we review your request and photos. Request a carpet cleaning quote →</Link>}
    <div className="grid gap-3 sm:grid-cols-2" data-testid="quote-service-options">
      {services.map((s) => <ChoiceCard key={s.key} active={form.service === s.key} onClick={() => set("service", s.key)} title={s.name}
        sub={s.from_price ? `From ${gbp(s.from_price)} · quoted after review` : s.requires_survey ? "Priced after a short survey" : `From ${gbp(s.min_price)}${isEot(s.key) ? " · move-out clean" : s.key === "regular" ? " · routine home clean" : ""}`} testid={`quote-service-${s.key}`} />)}
    </div>
    </>
  );
}

const Block = ({ label, children }) => <div><Label className="eyebrow">{label}</Label>{children}</div>;

export function StepProperty({ p, form, set }) {
  const eot = isEot(form.service);
  const toggleArea = (a) => set("additional_areas", form.additional_areas.includes(a) ? form.additional_areas.filter((x) => x !== a) : [...form.additional_areas, a]);
  return (
    <div className="space-y-8" data-testid={`property-step-${eot ? "eot" : "standard"}`}>
      <Block label="Property type">
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="quote-property-type-select">
          {p.property_types.map((t) => <ChoiceCard key={t.key} active={form.property_type === t.key} onClick={() => set("property_type", t.key)} title={t.name} testid={`quote-ptype-${t.key}`} />)}
        </div>
      </Block>
      <div className="grid gap-3">
        <Counter label="Bedrooms" value={form.bedrooms} onChange={(v) => set("bedrooms", v)} max={12} testid="quote-bedrooms-count" />
        <Counter label="Bathrooms" value={form.bathrooms} onChange={(v) => set("bathrooms", v)} testid="quote-bathrooms-count" />
        <Counter label="Living rooms" value={form.living_rooms} onChange={(v) => set("living_rooms", v)} max={6} testid="quote-living-count" />
      </div>
      <Block label="General condition">
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {p.conditions.map((c) => <ChoiceCard key={c.key} active={form.condition === c.key} onClick={() => set("condition", c.key)} title={c.name} testid={`quote-condition-${c.key}`} />)}
        </div>
      </Block>
      {eot && <Block label="Is the property furnished?"><Pills options={FURNISHED} value={form.furnished} onChange={(v) => set("furnished", v)} testid="quote-furnished" /></Block>}
      {eot && <Block label="Flooring (optional)"><Pills options={FLOORING} value={form.flooring} onChange={(v) => set("flooring", v)} testid="quote-flooring" /></Block>}
      <Block label="Pets"><Pills options={PETS} value={form.pets} onChange={(v) => set("pets", v)} testid="quote-pets" /></Block>
      {form.pets && form.pets !== "no" && (
        <label className="flex items-center gap-3 text-sm text-slate-700"><Checkbox checked={form.pet_hair_odour} onCheckedChange={(c) => set("pet_hair_odour", !!c)} data-testid="quote-pet-hair-checkbox" />There is significant pet hair or pet odour</label>
      )}
      <Block label="Additional rooms or areas to clean">
        <div className="mt-3 flex flex-wrap gap-2" data-testid="quote-additional-areas">
          {AREAS.map((a) => <button key={a} type="button" onClick={() => toggleArea(a)} data-testid={`quote-area-${a.split(" ")[0].toLowerCase()}`}
            className={`rounded-full border px-4 py-2 text-sm transition-colors ${form.additional_areas.includes(a) ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-200 bg-white text-slate-700"}`}>{a}</button>)}
        </div>
        <p className="mt-2 text-xs text-slate-500">Balconies and patios can be added as an extra in a later step.</p>
      </Block>
      <div><Label htmlFor="pnotes" className="eyebrow">Anything else about the property? (optional)</Label><Textarea id="pnotes" value={form.property_notes} onChange={(e) => set("property_notes", e.target.value)} className="mt-3 rounded-xl" data-testid="quote-property-notes-input" /></div>
    </div>
  );
}

export function StepExtras({ p, svc, form, set }) {
  const allowed = svc?.extras?.length ? p.extras.filter((x) => svc.extras.includes(x.key)) : p.extras;
  const excluded = new Set(form.extras.flatMap((k) => p.extras.find((x) => x.key === k)?.excludes || []));
  const toggle = (x, on) => {
    let next = on ? [...form.extras, x.key] : form.extras.filter((k) => k !== x.key);
    if (on && x.excludes) next = next.filter((k) => !x.excludes.includes(k));
    set("extras", next);
  };
  return (
    <div data-testid="extras-step">
      <div className="grid gap-3 sm:grid-cols-2">
        {allowed.map((x) => {
          const off = excluded.has(x.key);
          return (
            <label key={x.key} className={`flex cursor-pointer items-start justify-between gap-3 rounded-2xl border bg-white px-4 py-3 text-sm transition-colors ${form.extras.includes(x.key) ? "border-[#023F00]" : "border-slate-200 hover:border-[#8F7E22]"} ${off ? "opacity-50" : ""}`}>
              <span className="flex items-start gap-3">
                <Checkbox className="mt-0.5" disabled={off} checked={form.extras.includes(x.key) && !off} onCheckedChange={(c) => toggle(x, !!c)} data-testid={`quote-extra-${x.key}`} />
                <span><span className="font-medium text-slate-900">{x.name}</span>{x.description && <span className="mt-0.5 block text-xs text-slate-500">{x.description}</span>}{off && <span className="mt-0.5 block text-xs text-[#8F7E22]">Included in Freezer defrost</span>}</span>
              </span>
              <span className="whitespace-nowrap font-mono text-xs text-slate-600">+{gbp(x.price)}</span>
            </label>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-slate-500">Routine tasks such as taps, sinks, toilets and worktops are already part of your clean - no need to add them.</p>
    </div>
  );
}
