import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader2, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DemoTag, Empty, Kpi, PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, gbp, label } from "@/lib/api";

function Channels({ rows }) {
  const active = rows.filter((r) => r.leads || r.spend || r.revenue);
  return (
    <div className="overflow-x-auto">
      <Table data-testid="channel-table">
        <TableHeader><TableRow>{["Channel", "Leads", "Bookings", "Revenue", "Spend", "CPL", "CAC", "Profit"].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {active.map((r) => (
            <TableRow key={r.channel} data-testid={`channel-row-${r.channel}`}>
              <TableCell className="font-medium capitalize">{label(r.channel)}</TableCell>
              <TableCell className="font-mono">{r.leads}</TableCell>
              <TableCell className="font-mono">{r.bookings}</TableCell>
              <TableCell className="font-mono">{gbp(r.revenue)}</TableCell>
              <TableCell className="font-mono">{gbp(r.spend)}</TableCell>
              <TableCell className="font-mono">{gbp(r.cpl)}</TableCell>
              <TableCell className="font-mono">{gbp(r.cac)}</TableCell>
              <TableCell className={`font-mono font-semibold ${r.profit >= 0 ? "text-teal-700" : "text-red-600"}`}>{gbp(r.profit)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function Overview() {
  const [days, setDays] = useState("30");
  const [data, reload] = useLoad("/admin/overview", { days });
  const [running, setRunning] = useState(false);
  const run = async () => {
    setRunning(true);
    try {
      const { data: r } = await api.post("/admin/automations/run");
      toast.success(`Automations ran: ${r.quote_follow_ups_sent} quote follow-ups, ${r.scheduled_messages_sent} scheduled messages sent`);
      reload();
    } catch (e) { toast.error(errMsg(e)); }
    setRunning(false);
  };
  if (!data) return <p className="font-mono text-sm text-slate-500">Loading dashboard…</p>;
  const k = data.kpis;
  const chart = data.channels.filter((r) => r.leads || r.revenue || r.spend).map((r) => ({ name: label(r.channel), Revenue: r.revenue, Spend: r.spend }));

  return (
    <div data-testid="admin-overview-page">
      <PageHeader eyebrow="Command centre" title="Business overview" desc="Enquiries, bookings, revenue and marketing cost - attributed to the channel that first brought each customer.">
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-40 bg-white" data-testid="overview-period-select"><SelectValue /></SelectTrigger>
          <SelectContent>{[["30", "Last 30 days"], ["90", "Last 90 days"], ["365", "Last 12 months"], ["0", "All time"]].map(([v, t]) => <SelectItem key={v} value={v}>{t}</SelectItem>)}</SelectContent>
        </Select>
        <Button onClick={run} disabled={running} className="bg-slate-900 hover:bg-teal-700 hover:text-white" data-testid="overview-run-automations-btn">
          {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}Run automations
        </Button>
      </PageHeader>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi testid="crm-kpi-revenue" label="Revenue (paid)" value={gbp(k.revenue)} hint={`${gbp(k.completed_revenue)} from completed jobs`} accent />
        <Kpi testid="crm-kpi-new-leads" label="New leads" value={k.new_leads} hint={`${k.uncontacted_leads} not yet quoted`} />
        <Kpi testid="crm-kpi-quotes-awaiting" label="Quotes awaiting" value={k.quotes_awaiting} />
        <Kpi testid="crm-kpi-upcoming-jobs" label="Upcoming jobs" value={k.upcoming_jobs} hint={`${k.completed_jobs} completed`} />
        <Kpi testid="crm-kpi-ad-spend" label="Google Ads spend" value={gbp(k.ad_spend)} hint={`${gbp(k.marketing_spend)} all marketing`} />
        <Kpi testid="crm-kpi-cpl" label="Cost per lead" value={gbp(k.cpl)} />
        <Kpi testid="crm-kpi-cac" label="Customer acq. cost" value={gbp(k.cac)} />
        <Kpi testid="crm-kpi-conversion" label="Lead → booking" value={`${k.conversion_rate}%`} hint={`${k.repeat_customers} repeat customers`} />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title="Channel profitability" className="xl:col-span-2"><Channels rows={data.channels} /></Panel>
        <Panel title="Funnel">
          <div className="space-y-4" data-testid="overview-funnel">
            {data.funnel.map((f) => (
              <div key={f.stage}>
                <div className="flex justify-between text-sm"><span>{f.stage}</span><span className="font-mono font-semibold">{f.value}</span></div>
                <div className="mt-1.5 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-teal-600" style={{ width: `${data.funnel[0].value ? (f.value / data.funnel[0].value) * 100 : 0}%` }} /></div>
              </div>
            ))}
            <p className="pt-2 text-xs text-slate-400">Commercial opportunities in play: <b className="font-mono text-slate-700">{k.commercial_opportunities}</b></p>
          </div>
        </Panel>
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title="Revenue vs spend by channel" className="xl:col-span-2">
          <div className="h-72"><ResponsiveContainer><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend /><Bar dataKey="Revenue" fill="#0D9488" radius={[6, 6, 0, 0]} /><Bar dataKey="Spend" fill="#0F172A" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Panel>
        <Panel title={`Needs attention (${k.follow_ups_due})`}>
          <ul className="space-y-3 text-sm" data-testid="overview-follow-ups">
            {data.escalations.map((c) => <li key={c.id} className="rounded-xl bg-red-50 p-3"><Link to="/admin/receptionist" className="font-medium text-red-800">AI escalation</Link><p className="text-xs text-red-700">{c.escalation_reason}</p></li>)}
            {data.follow_ups.map((l) => <li key={l.id} className="rounded-xl bg-amber-50 p-3"><Link to="/admin/leads" className="font-medium text-amber-900">Follow up {l.name}</Link><DemoTag show={l.demo} /><p className="text-xs text-amber-800">Due {fmtDate(l.follow_up_date)} · {label(l.status)}</p></li>)}
            {!data.escalations.length && !data.follow_ups.length && <Empty>Nothing outstanding.</Empty>}
          </ul>
        </Panel>
      </div>
      <Panel title="Upcoming jobs" className="mt-6">
        {data.upcoming.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" data-testid="overview-upcoming-jobs">
            {data.upcoming.map((b) => (
              <div key={b.id} className="rounded-xl border border-slate-200 p-4">
                <p className="font-mono text-xs text-teal-700">{fmtDate(b.date)} · {b.slot}</p>
                <p className="mt-1 font-medium">{b.customer.name}<DemoTag show={b.demo} /></p>
                <p className="text-xs text-slate-500">{b.service_name} · {b.postcode} · {gbp(b.total)}</p>
              </div>
            ))}
          </div>
        ) : <Empty>No upcoming jobs.</Empty>}
      </Panel>
    </div>
  );
}
