import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DemoTag, Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { LEAD_STATUSES, LeadDrawer } from "@/components/admin/LeadDrawer";
import { SOURCES, api, errMsg, fmtDate, label } from "@/lib/api";

function AddLead({ open, setOpen, onDone }) {
  const [f, setF] = useState({ name: "", phone: "", email: "", postcode: "", source: "phone", type: "residential", notes: "" });
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post("/admin/leads", f); toast.success("Lead added"); setOpen(false); onDone(); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="add-lead-dialog">
        <DialogHeader><DialogTitle>Add lead (e.g. phone enquiry)</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          {["name", "phone", "email", "postcode"].map((k) => <Input key={k} required={k === "name"} placeholder={label(k)} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`add-lead-${k}-input`} />)}
          <Select value={f.source} onValueChange={(v) => setF({ ...f, source: v })}>
            <SelectTrigger data-testid="add-lead-source-select"><SelectValue /></SelectTrigger>
            <SelectContent>{SOURCES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={f.type} onValueChange={(v) => setF({ ...f, type: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="residential">Residential</SelectItem><SelectItem value="commercial">Commercial</SelectItem></SelectContent>
          </Select>
          <Button className="bg-teal-600 hover:bg-teal-700" data-testid="add-lead-submit-btn">Save lead</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Leads() {
  const [filters, setFilters] = useState({ status: "", source: "", q: "" });
  const [leads, reload] = useLoad("/admin/leads", filters);
  const [open, setOpen] = useState(null);
  const [adding, setAdding] = useState(false);
  const all = (v) => (v === "all" ? "" : v);

  return (
    <div data-testid="admin-leads-page">
      <PageHeader eyebrow="CRM" title="Leads & customers" desc="Every enquiry from the website, AI receptionist, phone, ads and outreach - with full history.">
        <Button onClick={() => setAdding(true)} className="bg-slate-900 hover:bg-teal-700" data-testid="leads-add-btn"><Plus className="mr-1 h-4 w-4" />Add lead</Button>
      </PageHeader>
      <div className="mb-4 flex flex-wrap gap-3">
        <Input placeholder="Search name, email, phone, postcode" className="w-72 bg-white" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} data-testid="leads-search-input" />
        <Select value={filters.status || "all"} onValueChange={(v) => setFilters({ ...filters, status: all(v) })}>
          <SelectTrigger className="w-40 bg-white" data-testid="leads-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All statuses</SelectItem>{LEAD_STATUSES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={filters.source || "all"} onValueChange={(v) => setFilters({ ...filters, source: all(v) })}>
          <SelectTrigger className="w-40 bg-white" data-testid="leads-source-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All sources</SelectItem>{SOURCES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["Name", "Contact", "Postcode", "Source", "Status", "Follow-up", "Created"].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {leads?.map((l) => (
              <TableRow key={l.id} className="cursor-pointer hover:bg-teal-50/50" onClick={() => setOpen(l.id)} data-testid="crm-lead-row">
                <TableCell className="font-medium">{l.name}<DemoTag show={l.demo} /></TableCell>
                <TableCell className="text-xs text-slate-500">{l.email}<br />{l.phone}</TableCell>
                <TableCell className="font-mono text-xs">{l.postcode}</TableCell>
                <TableCell className="capitalize">{label(l.source)}</TableCell>
                <TableCell><StatusBadge status={l.status} /></TableCell>
                <TableCell className="text-xs">{l.follow_up_date ? fmtDate(l.follow_up_date) : "—"}</TableCell>
                <TableCell className="text-xs">{fmtDate(l.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {leads?.length === 0 && <Empty>No leads match.</Empty>}
      </div>
      <LeadDrawer leadId={open} onClose={() => setOpen(null)} onSaved={reload} />
      <AddLead open={adding} setOpen={setAdding} onDone={reload} />
    </div>
  );
}
