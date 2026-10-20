import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";

const PER_MONTH = { weekly: 52 / 12, fortnightly: 26 / 12, monthly: 1 };
const TABS = ["all", "active", "paused", "cancelled"];

const Stat = ({ label, value, testid }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid={testid}>
    <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
  </div>
);

function Actions({ p, reload }) {
  const set = async (status) => { try { await api.post(`/admin/recurring/${p.id}/status`, { status }); toast.success(`Regular clean ${status}`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (p.status === "cancelled") return null;
  return (
    <div className="flex gap-1">
      {p.status === "active" && <Button size="sm" variant="outline" onClick={() => set("paused")} data-testid={`regular-pause-${p.id}`}>Pause</Button>}
      {p.status === "paused" && <Button size="sm" variant="outline" onClick={() => set("active")} data-testid={`regular-resume-${p.id}`}>Resume</Button>}
      <Button size="sm" variant="ghost" className="text-red-700" onClick={() => window.confirm(`Cancel ${p.customer.name}'s regular clean? No more visits will be charged.`) && set("cancelled")} data-testid={`regular-cancel-${p.id}`}>Cancel</Button>
    </div>
  );
}

export default function RegularClients() {
  const [rows, reload] = useLoad("/admin/recurring");
  const [tab, setTab] = useState("active");
  const list = (rows || []).filter((p) => tab === "all" || p.status === tab);
  const active = (rows || []).filter((p) => p.status === "active");
  const monthly = active.reduce((sum, p) => sum + p.total * (PER_MONTH[p.frequency] || 0), 0);
  return (
    <div data-testid="admin-regular-clients-page">
      <PageHeader eyebrow="Recurring" title="Regular clients" desc="Every weekly, fortnightly and monthly client, with their next visit and payment status. Saved cards are charged automatically 2 days before each visit." />
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active" value={active.length} testid="regular-stat-active" />
        <Stat label="Paused" value={(rows || []).filter((p) => p.status === "paused").length} testid="regular-stat-paused" />
        <Stat label="Last payment failed" value={active.filter((p) => p.last_result === "failed").length} testid="regular-stat-failed" />
        <Stat label="Expected per month" value={gbp(Math.round(monthly * 100) / 100)} testid="regular-stat-monthly" />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-full px-4 py-1.5 text-sm capitalize ${tab === t ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`} data-testid={`regular-tab-${t}`}>{t}</button>)}
      </div>
      {rows && !list.length ? <Empty>No {tab === "all" ? "" : tab} regular clients yet.</Empty> : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <Table data-testid="regular-clients-table">
            <TableHeader><TableRow><TableHead>Client</TableHead><TableHead>Frequency</TableHead><TableHead>Price / visit</TableHead><TableHead>Next visit</TableHead><TableHead>Status</TableHead><TableHead>Last visit</TableHead><TableHead>Card</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>
              {list.map((p) => (
                <TableRow key={p.id} data-testid={`regular-row-${p.id}`}>
                  <TableCell><b>{p.customer.name}</b><span className="block text-xs text-slate-500">{p.customer.phone} · {p.postcode}</span></TableCell>
                  <TableCell className="capitalize">{p.frequency}</TableCell>
                  <TableCell className="font-mono">{gbp(p.total)}</TableCell>
                  <TableCell className="whitespace-nowrap">{p.status === "active" ? `${fmtDate(p.next_date)} · ${p.slot}` : "-"}</TableCell>
                  <TableCell><StatusBadge status={p.status} /></TableCell>
                  <TableCell className="whitespace-nowrap text-sm">{p.last_visit ? <>{fmtDate(p.last_visit.date)} <StatusBadge status={p.last_visit.payment_status} /></> : "-"}<span className="block text-xs text-slate-400">{p.visits} visit{p.visits === 1 ? "" : "s"}</span></TableCell>
                  <TableCell className="text-sm">{p.card_saved ? "Saved" : <span className="text-red-700">Not saved</span>}</TableCell>
                  <TableCell><Actions p={p} reload={reload} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
