import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, Panel } from "@/components/admin/ui";
import { api, errMsg, label } from "@/lib/api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const num = (v) => (v === "" ? 0 : Number(v));
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

function NumTable({ rows, fields, onChange, testid }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid={testid}>
        <thead><tr className="text-left font-mono text-[10px] uppercase tracking-wider text-slate-500"><th className="py-2 pr-3">Name</th>{fields.map((f) => <th key={f} className="py-2 pr-3">{label(f)}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.key} className="border-t border-slate-100">
              <td className="py-2 pr-3"><Input value={r.name} onChange={(e) => onChange(i, "name", e.target.value)} className="min-w-[180px]" /></td>
              {fields.map((f) => (
                <td key={f} className="py-2 pr-3">
                  {typeof r[f] === "boolean"
                    ? <Switch checked={r[f]} onCheckedChange={(v) => onChange(i, f, v)} />
                    : <Input type="number" step="0.01" value={r[f]} onChange={(e) => onChange(i, f, num(e.target.value))} className="w-24 font-mono" data-testid={`${testid}-${r.key}-${f}`} />}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Settings() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/admin/settings").then((r) => setS(r.data)); }, []);
  if (!s) return <p className="font-mono text-sm">Loading…</p>;
  const p = s.pricing, av = s.availability;
  const setP = (k, v) => setS({ ...s, pricing: { ...p, [k]: v } });
  const setAv = (k, v) => setS({ ...s, availability: { ...av, [k]: v } });
  const editRow = (k) => (i, f, v) => setP(k, p[k].map((r, j) => (j === i ? { ...r, [f]: v } : r)));
  const save = async () => {
    try { await api.put("/admin/settings", { business: s.business, pricing: p, availability: av, knowledge_base: s.knowledge_base }); toast.success("Settings saved - AI receptionist and quote engine updated"); } catch (e) { toast.error(errMsg(e)); }
  };
  const clearDemo = async () => { const { data } = await api.delete("/admin/demo-data"); toast.success(`Removed ${data.removed} demo records`); };

  return (
    <div data-testid="admin-settings-page">
      <PageHeader eyebrow="Configuration" title="Settings" desc="The single source of truth for prices, availability and company knowledge - used by the website quote form and the AI receptionist alike.">
        <Button onClick={save} className="bg-teal-600 hover:bg-teal-700" data-testid="settings-save-btn">Save settings</Button>
      </PageHeader>
      <Tabs defaultValue="pricing">
        <TabsList className="flex-wrap">
          {["pricing", "availability", "knowledge", "business"].map((t) => <TabsTrigger key={t} value={t} className="capitalize" data-testid={`settings-tab-${t}`}>{t === "knowledge" ? "Knowledge base" : t}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="pricing" className="space-y-6">
          <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900" data-testid="settings-placeholder-notice">{p.placeholder_notice}</p>
          <Panel title="Services (£)"><NumTable rows={p.services} fields={["base", "per_bedroom", "per_bathroom", "per_living_room", "min_price", "requires_survey"]} onChange={editRow("services")} testid="settings-pricing-services" /></Panel>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Property type multipliers"><NumTable rows={p.property_types} fields={["multiplier"]} onChange={editRow("property_types")} testid="settings-ptypes" /></Panel>
            <Panel title="Condition multipliers"><NumTable rows={p.conditions} fields={["multiplier", "requires_review"]} onChange={editRow("conditions")} testid="settings-conditions" /></Panel>
            <Panel title="Extras (£)"><NumTable rows={p.extras} fields={["price"]} onChange={editRow("extras")} testid="settings-extras" /></Panel>
            <Panel title="Rules">
              <Label>No-parking surcharge (£)</Label>
              <Input type="number" className="mt-1 w-32 font-mono" value={p.parking_surcharge} onChange={(e) => setP("parking_surcharge", num(e.target.value))} data-testid="settings-pricing-base-rate-input" />
              <Label className="mt-4 block">Service area postcode prefixes (comma separated)</Label>
              <Input className="mt-1 font-mono" value={p.service_area_prefixes.join(", ")} onChange={(e) => setP("service_area_prefixes", list(e.target.value.toUpperCase()))} data-testid="settings-area-input" />
            </Panel>
          </div>
        </TabsContent>
        <TabsContent value="availability">
          <Panel>
            <Label>Working days</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {DAYS.map((d, i) => (
                <button key={d} type="button" onClick={() => setAv("working_days", av.working_days.includes(i) ? av.working_days.filter((x) => x !== i) : [...av.working_days, i].sort())}
                  className={`rounded-full px-4 py-1.5 text-sm ${av.working_days.includes(i) ? "bg-teal-600 text-white" : "bg-slate-100 text-slate-500"}`} data-testid={`settings-day-${d.toLowerCase()}`}>{d}</button>
              ))}
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div><Label>Start times (comma separated)</Label><Input className="mt-1 font-mono" value={av.slots.join(", ")} onChange={(e) => setAv("slots", list(e.target.value))} data-testid="settings-slots-input" /></div>
              <div><Label>Teams per slot (capacity)</Label><Input type="number" className="mt-1 font-mono" value={av.capacity_per_slot} onChange={(e) => setAv("capacity_per_slot", num(e.target.value))} data-testid="settings-capacity-input" /></div>
              <div><Label>Minimum notice (days)</Label><Input type="number" className="mt-1 font-mono" value={av.min_notice_days} onChange={(e) => setAv("min_notice_days", num(e.target.value))} /></div>
              <div><Label>Book up to (days ahead)</Label><Input type="number" className="mt-1 font-mono" value={av.max_advance_days} onChange={(e) => setAv("max_advance_days", num(e.target.value))} /></div>
              <div className="sm:col-span-2"><Label>Blocked dates (YYYY-MM-DD, comma separated)</Label><Input className="mt-1 font-mono" value={av.blocked_dates.join(", ")} onChange={(e) => setAv("blocked_dates", list(e.target.value))} data-testid="settings-blocked-input" /></div>
            </div>
          </Panel>
        </TabsContent>
        <TabsContent value="knowledge" className="space-y-3">
          {s.knowledge_base.map((k, i) => (
            <div key={i} className="grid gap-2 rounded-2xl border border-slate-200 bg-white p-4 md:grid-cols-[1fr_2fr_auto]" data-testid="settings-kb-item">
              <Input value={k.q} onChange={(e) => setS({ ...s, knowledge_base: s.knowledge_base.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)) })} />
              <Textarea rows={2} value={k.a} onChange={(e) => setS({ ...s, knowledge_base: s.knowledge_base.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)) })} />
              <button onClick={() => setS({ ...s, knowledge_base: s.knowledge_base.filter((_, j) => j !== i) })} className="text-slate-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
          <Button variant="outline" onClick={() => setS({ ...s, knowledge_base: [...s.knowledge_base, { q: "", a: "" }] })} data-testid="settings-kb-add-btn"><Plus className="mr-1 h-4 w-4" />Add entry</Button>
        </TabsContent>
        <TabsContent value="business">
          <Panel>
            <div className="grid gap-4 sm:grid-cols-2">
              {Object.entries(s.business).map(([k, v]) => (
                <div key={k}><Label className="capitalize">{label(k)}</Label>
                  <Input className="mt-1" value={v} onChange={(e) => setS({ ...s, business: { ...s.business, [k]: typeof v === "number" ? num(e.target.value) : e.target.value } })} data-testid={`settings-business-${k}`} />
                </div>
              ))}
            </div>
            <div className="mt-8 border-t border-slate-100 pt-5">
              <p className="text-sm text-slate-600">Demo records (tagged "demo") were added so the dashboard isn't empty. Remove them before going live.</p>
              <Button variant="destructive" className="mt-3" onClick={clearDemo} data-testid="settings-clear-demo-btn">Clear demo data</Button>
            </div>
          </Panel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
