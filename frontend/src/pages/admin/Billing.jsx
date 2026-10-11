import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Panel, StatusBadge } from "@/components/admin/ui";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";
import { FEATURES } from "@/lib/tenant";

function PlanCard({ p, interval, current, busy, onChoose }) {
  const price = interval === "month" ? p.monthly_price : p.annual_price;
  return (
    <div className={`flex flex-col rounded-2xl border p-6 ${current ? "border-teal-600 ring-1 ring-teal-600" : "border-slate-200"} bg-white`} data-testid={`plan-card-${p.key}`}>
      <p className="font-display text-xl font-semibold">{p.name}</p>
      <p className="mt-1 text-sm text-slate-500">{p.description}</p>
      <p className="mt-5 font-mono text-3xl font-bold">{gbp(price)}<span className="text-sm font-normal text-slate-500">/{interval === "month" ? "mo" : "yr"}</span></p>
      <ul className="mt-5 flex-1 space-y-2 text-sm">
        {FEATURES.filter(([k]) => p.features.includes(k)).map(([k, l]) => <li key={k} className="flex gap-2"><Check className="h-4 w-4 text-teal-600" />{l}</li>)}
        <li className="flex gap-2"><Check className="h-4 w-4 text-teal-600" />Up to {p.max_staff} users</li>
      </ul>
      <Button disabled={current || busy} onClick={() => onChoose(p.key)} className="mt-6 bg-slate-900 hover:bg-teal-700" data-testid={`plan-choose-btn-${p.key}`}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : current ? "Current plan" : "Choose plan"}
      </Button>
    </div>
  );
}

export default function Billing() {
  const { user, refresh } = useAuth();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [interval, setInterval] = useState("month");
  const [busy, setBusy] = useState("");
  const owner = user.role === "owner";

  useEffect(() => {
    const sid = params.get("session_id");
    api.get("/billing/sync", { params: sid ? { session_id: sid } : {} })
      .then((r) => { setData(r.data); setInterval(r.data.company.billing_interval || "month"); if (sid) { toast.success("Subscription updated"); setParams({}); refresh(); } })
      .catch((e) => toast.error(errMsg(e)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (name, fn) => {
    setBusy(name);
    try { await fn(); } catch (e) { toast.error(errMsg(e)); }
    setBusy("");
  };
  const choose = (plan_key) => act(plan_key, async () => {
    const { data: r } = await api.post("/billing/checkout", { plan_key, interval, origin_url: window.location.origin });
    if (r.checkout_url) { window.location.href = r.checkout_url; return; }
    toast.success("Plan changed - prorated on your next invoice");
    setData((await api.get("/billing/summary")).data);
    refresh();
  });
  const toggleCancel = (path) => act(path, async () => { setData((await api.post(`/billing/${path}`)).data); toast.success(path === "cancel" ? "Subscription will end at period end" : "Subscription resumed"); refresh(); });
  const portal = () => act("portal", async () => { window.location.href = (await api.post("/billing/portal", { origin_url: window.location.origin })).data.url; });

  if (!data) return <p className="font-mono text-sm">Loading billing…</p>;
  const c = data.company;
  const paid = !!c.stripe_subscription_id;
  return (
    <div data-testid="admin-billing-page">
      <PageHeader eyebrow="Subscription" title="Plan & billing" desc="Pay monthly or annually by card via Stripe. Upgrade, downgrade or cancel at any time." />
      {!data.access.ok && <div className="mb-6 rounded-2xl bg-red-50 p-4 text-sm text-red-800" data-testid="billing-locked-notice"><b>Access restricted:</b> {data.access.reason}. Choose a plan below to restore access.</div>}
      <Panel title="Current subscription" className="mb-6">
        <div className="flex flex-wrap items-center gap-6 text-sm" data-testid="billing-current">
          <span>Plan: <b className="capitalize">{c.plan_key}</b></span>
          <StatusBadge status={c.comped ? "complimentary" : c.subscription_status} testid="billing-status" />
          {c.subscription_status === "trialing" && <span>Trial ends {fmtDate(c.trial_ends_at)}</span>}
          {c.current_period_end && <span>{c.cancel_at_period_end ? "Ends" : "Renews"} {fmtDate(c.current_period_end)} ({c.billing_interval}ly)</span>}
          {owner && paid && (
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" onClick={portal} disabled={!!busy} data-testid="billing-portal-btn">Payment method & invoices</Button>
              {c.cancel_at_period_end
                ? <Button size="sm" onClick={() => toggleCancel("resume")} disabled={!!busy} data-testid="billing-resume-btn">Resume</Button>
                : <Button size="sm" variant="destructive" onClick={() => toggleCancel("cancel")} disabled={!!busy} data-testid="billing-cancel-btn">Cancel subscription</Button>}
            </div>
          )}
        </div>
      </Panel>
      <div className="mb-4 inline-flex rounded-full bg-slate-100 p-1" data-testid="billing-interval-toggle">
        {[["month", "Monthly"], ["year", "Annual (2 months free)"]].map(([v, t]) => (
          <button key={v} onClick={() => setInterval(v)} className={`rounded-full px-4 py-1.5 text-sm ${interval === v ? "bg-white shadow" : "text-slate-500"}`} data-testid={`billing-interval-${v}`}>{t}</button>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {data.plans.map((p) => (
          <PlanCard key={p.id} p={p} interval={interval} busy={busy === p.key} onChoose={owner ? choose : () => toast.error("Only the account owner can change the plan")}
            current={paid && c.subscription_status === "active" && c.plan_key === p.key && c.billing_interval === interval} />
        ))}
      </div>
      <Panel title="Invoices" className="mt-6">
        <Table>
          <TableHeader><TableRow>{["Date", "Amount", "Status", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {data.invoices.map((i) => (
              <TableRow key={i.id} data-testid="invoice-row"><TableCell>{fmtDate(i.created_at)}</TableCell><TableCell className="font-mono">{gbp(i.amount_due)}</TableCell><TableCell><StatusBadge status={i.status} /></TableCell>
                <TableCell>{i.url && <a href={i.url} target="_blank" rel="noreferrer" className="text-teal-700 hover:underline">View</a>}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
        {!data.invoices.length && <p className="py-4 text-center text-sm text-slate-400">No invoices yet.</p>}
      </Panel>
    </div>
  );
}
