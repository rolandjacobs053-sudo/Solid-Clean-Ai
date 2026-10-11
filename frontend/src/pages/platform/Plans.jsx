import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/api";
import { FEATURES } from "@/lib/tenant";

const BLANK = { key: "", name: "", description: "", monthly_price: 0, annual_price: 0, max_staff: 5, features: ["quotes_bookings", "crm"], active: true, order: 9 };

function PlanEditor({ plan, onSaved, isNew }) {
  const [p, setP] = useState(plan);
  const save = async () => {
    try { await api.put("/platform/plans", { ...p, monthly_price: Number(p.monthly_price), annual_price: Number(p.annual_price), max_staff: Number(p.max_staff), order: Number(p.order) }); toast.success("Plan saved & synced to Stripe"); onSaved(); if (isNew) setP(BLANK); } catch (e) { toast.error(errMsg(e)); }
  };
  const tid = p.key || "new";
  return (
    <Panel title={isNew ? "New plan" : p.name} action={<span className="flex items-center gap-2 text-xs">Active<Switch checked={p.active} onCheckedChange={(v) => setP({ ...p, active: v })} /></span>}>
      <div className="grid gap-3 sm:grid-cols-2">
        {[["key", "Key (lowercase)"], ["name", "Name"], ["monthly_price", "Monthly £"], ["annual_price", "Annual £"], ["max_staff", "Max users"], ["order", "Display order"]].map(([k, l]) => (
          <div key={k}><Label className="text-xs">{l}</Label><Input className="mt-1" disabled={k === "key" && !isNew} value={p[k]} onChange={(e) => setP({ ...p, [k]: e.target.value })} data-testid={`plan-${tid}-${k}-input`} /></div>
        ))}
        <div className="sm:col-span-2"><Label className="text-xs">Description</Label><Input className="mt-1" value={p.description} onChange={(e) => setP({ ...p, description: e.target.value })} /></div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {FEATURES.map(([k, l]) => (
          <label key={k} className="flex items-center gap-2 text-sm"><Checkbox checked={p.features.includes(k)} onCheckedChange={(c) => setP({ ...p, features: c ? [...p.features, k] : p.features.filter((x) => x !== k) })} data-testid={`plan-${tid}-feature-${k}`} />{l}</label>
        ))}
      </div>
      <Button onClick={save} className="mt-4 bg-teal-600 hover:bg-teal-700" data-testid={`plan-${tid}-save-btn`}>Save plan</Button>
    </Panel>
  );
}

export default function Plans() {
  const [plans, reload] = useLoad("/platform/plans");
  return (
    <div data-testid="platform-plans-page">
      <PageHeader eyebrow="Pricing" title="Subscription plans" desc="Placeholder plans - edit names, prices, user limits and features. Price changes create new Stripe prices for new subscribers; existing subscribers keep their price until they change plan." />
      <div className="grid gap-6 xl:grid-cols-2">
        {plans?.map((p) => <PlanEditor key={p.id} plan={p} onSaved={reload} />)}
        <PlanEditor plan={BLANK} onSaved={reload} isNew />
      </div>
    </div>
  );
}
