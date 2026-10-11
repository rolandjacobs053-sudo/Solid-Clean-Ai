import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Kpi, PageHeader, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, gbp, label } from "@/lib/api";

export default function PlatformOverview() {
  const [d, reload] = useLoad("/platform/overview");
  const toggle = async (v) => { try { await api.patch("/platform/settings", { signup_enabled: v }); toast.success(v ? "Sign-ups & subscriptions OPEN" : "Sign-ups & subscriptions closed"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (!d) return <p className="font-mono text-sm">Loading…</p>;
  return (
    <div data-testid="platform-overview-page">
      <PageHeader eyebrow="SaaS metrics" title="Platform overview" desc="Recurring revenue and subscription health across all cleaning companies." />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" data-testid="saas-launch-panel">
        <span><b>SaaS launch:</b> {d.signup_enabled ? "OPEN - new companies can sign up and be charged." : "CLOSED - no new sign-ups and no subscription charges until you approve pricing, terms and launch."}</span>
        <label className="flex items-center gap-2">Open sign-ups<Switch checked={d.signup_enabled} onCheckedChange={toggle} data-testid="saas-signup-toggle" /></label>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi testid="platform-kpi-mrr" label="MRR" value={gbp(d.mrr)} hint={`ARR ${gbp(d.arr)}`} accent />
        <Kpi testid="platform-kpi-companies" label="Companies" value={d.companies} hint={`${d.signups_30d} new in 30 days`} />
        <Kpi testid="platform-kpi-collected" label="Collected (all time)" value={gbp(d.collected)} />
        <Kpi testid="platform-kpi-failed" label="Unpaid invoices" value={d.failed_payments} />
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Panel title="By subscription status"><ul className="space-y-2">{Object.entries(d.by_status).map(([k, v]) => <li key={k} className="flex justify-between"><StatusBadge status={k} /><span className="font-mono">{v}</span></li>)}</ul></Panel>
        <Panel title="By plan"><ul className="space-y-2">{d.by_plan.map((p) => <li key={p.plan} className="flex justify-between capitalize"><span>{label(p.plan)}</span><span className="font-mono">{p.companies}</span></li>)}</ul></Panel>
      </div>
    </div>
  );
}
