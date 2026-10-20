import { Copy, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/components/admin/ui";

const num = (v) => (v === "" ? 0 : Number(v));
const NEW = { name: "New service", description: "", pricing_mode: "per_room", fixed_price: 0, base: 0, per_bedroom: 0, per_bathroom: 0, per_living_room: 0,
  min_price: 0, requires_survey: false, active: false, online_booking: true, internal_notes: "", extras: [], scope_included: "", scope_excluded: "", preparation: "" };
const uid = (name) => `${name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 24)}_${Date.now().toString(36).slice(-4)}`;

function Field({ label, children }) {
  return <div><Label className="text-xs text-slate-500">{label}</Label><div className="mt-1">{children}</div></div>;
}

function ServiceCard({ s, extras, onChange, onDuplicate, onRemove }) {
  const set = (k, v) => onChange({ ...s, [k]: v });
  const numIn = (k) => <Input type="number" step="0.01" value={s[k] ?? 0} onChange={(e) => set(k, num(e.target.value))} className="font-mono" data-testid={`svc-${s.key}-${k}`} />;
  return (
    <div className={`rounded-2xl border bg-white p-5 ${s.active === false ? "border-dashed border-slate-300 opacity-80" : "border-slate-200"}`} data-testid={`service-card-${s.key}`}>
      <div className="flex flex-wrap items-center gap-3">
        <Input value={s.name} onChange={(e) => set("name", e.target.value)} className="max-w-sm font-display font-semibold" data-testid={`svc-${s.key}-name`} />
        <label className="flex items-center gap-2 text-xs">Active<Switch checked={s.active !== false} onCheckedChange={(v) => set("active", v)} data-testid={`svc-${s.key}-active`} /></label>
        <label className="flex items-center gap-2 text-xs">Online booking<Switch checked={s.online_booking !== false} onCheckedChange={(v) => set("online_booking", v)} data-testid={`svc-${s.key}-online`} /></label>
        <label className="flex items-center gap-2 text-xs">Quote after survey<Switch checked={!!s.requires_survey} onCheckedChange={(v) => set("requires_survey", v)} /></label>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" onClick={onDuplicate} data-testid={`svc-${s.key}-duplicate`}><Copy className="h-4 w-4" /></Button>
          <Button size="sm" variant="ghost" onClick={onRemove} className="text-red-600" data-testid={`svc-${s.key}-remove`}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Pricing">
          <select value={s.pricing_mode || "per_room"} onChange={(e) => set("pricing_mode", e.target.value)} className="h-9 w-full rounded-md border px-2 text-sm" data-testid={`svc-${s.key}-mode`}>
            <option value="per_room">By rooms</option><option value="fixed">Fixed price</option><option value="from">Starting price (quote)</option>
          </select>
        </Field>
        {s.pricing_mode && s.pricing_mode !== "per_room"
          ? <Field label="Price £">{numIn("fixed_price")}</Field>
          : <><Field label="Base £">{numIn("base")}</Field><Field label="Per bedroom £">{numIn("per_bedroom")}</Field><Field label="Per bathroom £">{numIn("per_bathroom")}</Field><Field label="Per living room £">{numIn("per_living_room")}</Field></>}
        <Field label="Minimum booking £">{numIn("min_price")}</Field>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Field label="Description (shown to customers)"><Textarea rows={2} value={s.description || ""} onChange={(e) => set("description", e.target.value)} /></Field>
        <Field label="Internal notes (never shown to customers)"><Textarea rows={2} value={s.internal_notes || ""} onChange={(e) => set("internal_notes", e.target.value)} data-testid={`svc-${s.key}-notes`} /></Field>
        <Field label="Included"><Textarea rows={2} value={s.scope_included || ""} onChange={(e) => set("scope_included", e.target.value)} /></Field>
        <Field label="Excluded"><Textarea rows={2} value={s.scope_excluded || ""} onChange={(e) => set("scope_excluded", e.target.value)} /></Field>
        <Field label="Customer preparation"><Textarea rows={2} value={s.preparation || ""} onChange={(e) => set("preparation", e.target.value)} /></Field>
        <Field label="Available extras (none ticked = all)">
          <div className="flex flex-wrap gap-3">{extras.map((x) => (
            <label key={x.key} className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={(s.extras || []).includes(x.key)} onChange={(e) => set("extras", e.target.checked ? [...(s.extras || []), x.key] : s.extras.filter((k) => k !== x.key))} />{x.name}</label>
          ))}</div>
        </Field>
      </div>
    </div>
  );
}

export function ServicesEditor({ pricing, setP }) {
  const list = pricing.services;
  const update = (i, v) => setP("services", list.map((s, j) => (j === i ? v : s)));
  return (
    <div className="space-y-4" data-testid="services-editor">
      {list.map((s, i) => (
        <ServiceCard key={s.key} s={s} extras={pricing.extras} onChange={(v) => update(i, v)}
          onDuplicate={() => setP("services", [...list.slice(0, i + 1), { ...s, key: uid(s.name), name: `${s.name} (copy)`, active: false }, ...list.slice(i + 1)])}
          onRemove={() => window.confirm?.(`Remove ${s.name}? Existing bookings keep their agreed price.`) !== false && setP("services", list.filter((_, j) => j !== i))} />
      ))}
      <Button variant="outline" onClick={() => setP("services", [...list, { ...NEW, key: uid("service") }])} data-testid="services-add-btn"><Plus className="mr-1 h-4 w-4" />Add service</Button>
    </div>
  );
}

export function ExtrasEditor({ pricing, setP }) {
  const rows = pricing.extras;
  const set = (i, k, v) => setP("extras", rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const add = () => setP("extras", [...rows, { key: `extra_${Date.now().toString(36)}`, name: "New extra", price: 0 }]);
  return (
    <Panel title="Extras (£) - shown on the booking form">
      <div className="space-y-2" data-testid="settings-extras">
        {rows.map((r, i) => (
          <div key={r.key} className="grid grid-cols-12 items-center gap-2 border-t border-slate-100 pt-2">
            <Input className="col-span-12 sm:col-span-4" value={r.name} onChange={(e) => set(i, "name", e.target.value)} data-testid={`settings-extras-${r.key}-name`} />
            <Input className="col-span-3 font-mono sm:col-span-2" type="number" step="0.01" value={r.price} onChange={(e) => set(i, "price", Number(e.target.value || 0))} data-testid={`settings-extras-${r.key}-price`} />
            <label className="col-span-4 flex items-center gap-1.5 text-xs sm:col-span-2"><Switch checked={!!r.per_item} onCheckedChange={(v) => set(i, "per_item", v)} data-testid={`settings-extras-${r.key}-per-item`} />Per item</label>
            {r.per_item ? <>
              <Input className="col-span-3 sm:col-span-2" placeholder="unit e.g. blind" value={r.unit || ""} onChange={(e) => set(i, "unit", e.target.value)} data-testid={`settings-extras-${r.key}-unit`} />
              <Input className="col-span-2 font-mono sm:col-span-1" type="number" min="1" title="Max quantity" value={r.max_qty || 20} onChange={(e) => set(i, "max_qty", Number(e.target.value || 1))} />
            </> : <span className="col-span-5 sm:col-span-3" />}
            <Button size="icon" variant="ghost" className="col-span-12 justify-self-end sm:col-span-1" onClick={() => setP("extras", rows.filter((_, j) => j !== i))} data-testid={`settings-extras-${r.key}-remove`}><Trash2 className="h-4 w-4" /></Button>
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={add} data-testid="settings-extras-add"><Plus className="mr-1 h-4 w-4" />Add extra</Button>
        <p className="text-xs text-slate-500">Per item extras show a quantity selector to customers (e.g. 4 blinds × £8). Tick which extras each service offers in the service cards above.</p>
      </div>
    </Panel>
  );
}

export function RulesEditor({ pricing, setP }) {
  const sn = pricing.short_notice || { days: 2, type: "percent", value: 0 };
  const promos = pricing.promo_codes || [];
  const setPromo = (i, k, v) => setP("promo_codes", promos.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel title="Emergency / short-notice surcharge">
        <div className="grid grid-cols-3 gap-3">
          <Field label="Within (days)"><Input type="number" value={sn.days} onChange={(e) => setP("short_notice", { ...sn, days: num(e.target.value) })} data-testid="rules-sn-days" /></Field>
          <Field label="Type"><select value={sn.type} onChange={(e) => setP("short_notice", { ...sn, type: e.target.value })} className="h-9 w-full rounded-md border px-2 text-sm"><option value="percent">%</option><option value="fixed">£ fixed</option></select></Field>
          <Field label="Amount (0 = off)"><Input type="number" value={sn.value} onChange={(e) => setP("short_notice", { ...sn, value: num(e.target.value) })} data-testid="rules-sn-value" /></Field>
        </div>
      </Panel>
      <Panel title="Discounts & promo codes">
        <div className="space-y-2">
          {promos.map((x, i) => (
            <div key={i} className="grid grid-cols-[1fr_70px_80px_1fr_70px_auto_auto] items-center gap-2 text-xs" data-testid="promo-row">
              <Input value={x.code} onChange={(e) => setPromo(i, "code", e.target.value.toUpperCase())} placeholder="CODE" className="font-mono" data-testid={`promo-${i}-code`} />
              <select value={x.type} onChange={(e) => setPromo(i, "type", e.target.value)} className="h-9 rounded-md border px-1"><option value="percent">%</option><option value="fixed">£</option></select>
              <Input type="number" value={x.value} onChange={(e) => setPromo(i, "value", num(e.target.value))} data-testid={`promo-${i}-value`} />
              <Input type="date" value={x.expires || ""} onChange={(e) => setPromo(i, "expires", e.target.value)} />
              <Input type="number" placeholder="Max" value={x.max_uses || ""} onChange={(e) => setPromo(i, "max_uses", num(e.target.value))} />
              <Switch checked={!!x.active} onCheckedChange={(v) => setPromo(i, "active", v)} data-testid={`promo-${i}-active`} />
              <button onClick={() => setP("promo_codes", promos.filter((_, j) => j !== i))} className="text-slate-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
          <p className="text-[11px] text-slate-400">Code · type · value · expiry · max uses · active. Used {promos.reduce((a, x) => a + (x.uses || 0), 0)} times in total.</p>
          <Button size="sm" variant="outline" onClick={() => setP("promo_codes", [...promos, { code: "", type: "percent", value: 10, expires: "", max_uses: 0, uses: 0, active: false }])} data-testid="promo-add-btn"><Plus className="mr-1 h-4 w-4" />Add code</Button>
        </div>
      </Panel>
    </div>
  );
}
