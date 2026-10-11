import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";

export default function Companies() {
  const [rows, reload] = useLoad("/platform/companies");
  const patch = async (c, body, msg) => { try { await api.patch(`/platform/companies/${c.id}`, body); toast.success(msg); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div data-testid="platform-companies-page">
      <PageHeader eyebrow="Tenants" title="Companies" desc="Every cleaning company on the platform, with plan, billing status and usage." />
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["Company", "Owner", "Plan", "Status", "Access", "MRR", "Users", "Leads", "Bookings", "Created", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows?.map((c) => (
              <TableRow key={c.id} data-testid="company-row">
                <TableCell className="font-medium">{c.name}<p className="font-mono text-[10px] text-slate-400">/c/{c.slug}</p></TableCell>
                <TableCell className="text-xs">{c.owner_email}</TableCell>
                <TableCell className="capitalize">{c.plan_key} · {c.billing_interval}</TableCell>
                <TableCell><StatusBadge status={c.comped ? "complimentary" : c.subscription_status} />{c.subscription_status === "trialing" && <p className="text-[10px] text-slate-400">until {fmtDate(c.trial_ends_at)}</p>}</TableCell>
                <TableCell>{c.access.ok ? <span className="text-xs text-teal-700">OK</span> : <span className="text-xs text-red-600">{c.access.reason}</span>}</TableCell>
                <TableCell className="font-mono">{gbp(c.mrr)}</TableCell><TableCell className="font-mono">{c.users}</TableCell><TableCell className="font-mono">{c.leads}</TableCell><TableCell className="font-mono">{c.bookings}</TableCell>
                <TableCell className="text-xs">{fmtDate(c.created_at)}</TableCell>
                <TableCell className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => patch(c, { extend_trial_days: 14 }, "Trial extended by 14 days")} data-testid={`company-extend-btn-${c.id}`}>+14d trial</Button>
                  <Button size="sm" variant={c.suspended ? "default" : "destructive"} onClick={() => patch(c, { suspended: !c.suspended }, c.suspended ? "Reactivated" : "Suspended")} data-testid={`company-suspend-btn-${c.id}`}>{c.suspended ? "Reactivate" : "Suspend"}</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
