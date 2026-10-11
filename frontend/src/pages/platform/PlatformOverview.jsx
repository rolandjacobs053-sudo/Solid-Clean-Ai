import { Kpi, PageHeader, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { gbp, label } from "@/lib/api";

export default function PlatformOverview() {
  const [d] = useLoad("/platform/overview");
  if (!d) return <p className="font-mono text-sm">Loading…</p>;
  return (
    <div data-testid="platform-overview-page">
      <PageHeader eyebrow="SaaS metrics" title="Platform overview" desc="Recurring revenue and subscription health across all cleaning companies." />
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
