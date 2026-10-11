import { useState } from "react";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DemoTag, PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, gbp, label } from "@/lib/api";

const SPEND_CHANNELS = ["google_ads", "seo", "cold_email", "whatsapp", "other"];
const INTEGRATIONS = [
  ["Google Ads", "Campaign spend, clicks and conversions imported daily; offline conversion upload of paid bookings (gclid) so bidding optimises for profit.", "Phase 4"],
  ["Google Search Console", "Queries, rankings and pages for South London & Surrey keywords; monthly SEO report.", "Phase 4"],
  ["Google Analytics 4", "Traffic, landing-page conversion, quote-started → booking funnel events.", "Phase 4"],
  ["Google Business Profile", "Reviews sync, reply publishing, local insights.", "Phase 4"],
  ["Website (WordPress)", "Embed the instant-quote flow / chat widget, UTM + gclid capture already live in this app.", "Phase 2"],
];

export default function Marketing() {
  const [rows, reload] = useLoad("/admin/spend");
  const [f, setF] = useState({ channel: "google_ads", month: new Date().toISOString().slice(0, 7), amount: "", notes: "" });
  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/admin/spend", { ...f, amount: Number(f.amount) }); toast.success("Spend recorded"); setF({ ...f, amount: "", notes: "" }); reload(); } catch (err) { toast.error(errMsg(err)); }
  };
  const del = async (id) => { await api.delete(`/admin/spend/${id}`); reload(); };
  return (
    <div data-testid="admin-marketing-page">
      <PageHeader eyebrow="Marketing" title="Spend, SEO & ads" desc="Record monthly marketing spend per channel - the overview uses it to calculate cost per lead, CAC and channel profit." />
      <div className="grid gap-6 xl:grid-cols-5">
        <Panel title="Monthly spend" className="xl:col-span-3">
          <form onSubmit={add} className="mb-5 grid gap-2 sm:grid-cols-5">
            <Select value={f.channel} onValueChange={(v) => setF({ ...f, channel: v })}>
              <SelectTrigger data-testid="spend-channel-select"><SelectValue /></SelectTrigger>
              <SelectContent>{SPEND_CHANNELS.map((c) => <SelectItem key={c} value={c}>{label(c)}</SelectItem>)}</SelectContent>
            </Select>
            <Input type="month" value={f.month} onChange={(e) => setF({ ...f, month: e.target.value })} data-testid="spend-month-input" />
            <Input type="number" step="0.01" min="0" required placeholder="£ amount" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="spend-amount-input" />
            <Input placeholder="Notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
            <Button className="bg-teal-600 hover:bg-teal-700" data-testid="spend-add-btn">Add</Button>
          </form>
          <Table>
            <TableHeader><TableRow>{["Month", "Channel", "Amount", "Notes", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {rows?.map((r) => (
                <TableRow key={r.id} data-testid="spend-row">
                  <TableCell className="font-mono">{r.month}</TableCell><TableCell className="capitalize">{label(r.channel)}<DemoTag show={r.demo} /></TableCell>
                  <TableCell className="font-mono">{gbp(r.amount)}</TableCell><TableCell className="text-xs text-slate-500">{r.notes}</TableCell>
                  <TableCell><button onClick={() => del(r.id)} className="text-slate-400 hover:text-red-600" data-testid={`spend-delete-${r.id}`}><Trash2 className="h-4 w-4" /></button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
        <Panel title="Integrations roadmap" className="xl:col-span-2">
          <ul className="space-y-4">
            {INTEGRATIONS.map(([t, d, ph]) => (
              <li key={t} className="rounded-xl border border-dashed border-slate-300 p-4" data-testid="integration-card">
                <div className="flex items-center justify-between"><p className="font-display font-semibold">{t}</p><span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[10px] uppercase">{ph} · not connected</span></div>
                <p className="mt-1 text-xs text-slate-500">{d}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
