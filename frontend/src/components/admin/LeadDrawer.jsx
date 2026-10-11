import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/admin/ui";
import { api, errMsg, fmtDate, fmtDateTime, gbp, label } from "@/lib/api";

export const LEAD_STATUSES = ["new", "quoted", "booked", "completed", "lost"];

const Section = ({ title, children }) => (
  <div className="mt-6"><p className="eyebrow">{title}</p><div className="mt-2 space-y-2">{children}</div></div>
);

export function LeadDrawer({ leadId, onClose, onSaved }) {
  const [d, setD] = useState(null);
  const [edit, setEdit] = useState({});
  useEffect(() => {
    if (!leadId) return;
    setD(null);
    api.get(`/admin/leads/${leadId}`).then((r) => { setD(r.data); setEdit({ status: r.data.lead.status, notes: r.data.lead.notes || "", follow_up_date: r.data.lead.follow_up_date || "" }); });
  }, [leadId]);

  const save = async () => {
    try {
      await api.patch(`/admin/leads/${leadId}`, { ...edit, follow_up_date: edit.follow_up_date || null });
      toast.success("Lead updated");
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Sheet open={!!leadId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl" data-testid="lead-drawer">
        {!d ? <p className="font-mono text-sm">Loading…</p> : (
          <>
            <SheetHeader><SheetTitle className="font-display text-2xl">{d.lead.name}</SheetTitle></SheetHeader>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-slate-600">
              <span data-testid="lead-drawer-email">{d.lead.email || "—"}</span><span>{d.lead.phone || "—"}</span>
              <span className="font-mono">{d.lead.postcode || "—"}</span><span>Source: <b className="capitalize">{label(d.lead.source)}</b></span>
              <span>Marketing consent: <b>{d.lead.marketing_consent ? "yes" : "no"}</b></span>
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3">
              <div><Label>Status</Label>
                <Select value={edit.status} onValueChange={(v) => setEdit({ ...edit, status: v })}>
                  <SelectTrigger className="mt-1" data-testid="lead-drawer-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{LEAD_STATUSES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Follow-up date</Label><Input type="date" className="mt-1" value={edit.follow_up_date} onChange={(e) => setEdit({ ...edit, follow_up_date: e.target.value })} data-testid="lead-drawer-followup-input" /></div>
              <div className="col-span-2"><Label>Notes</Label><Textarea className="mt-1" value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} data-testid="lead-drawer-notes-input" /></div>
            </div>
            <Button onClick={save} className="mt-3 bg-teal-600 hover:bg-teal-700" data-testid="lead-drawer-save-btn">Save changes</Button>
            <Section title="Quotes">
              {d.quotes.map((q) => <div key={q.id} className="flex justify-between rounded-lg bg-slate-50 p-3 text-sm"><span>{q.service_name} · {fmtDate(q.created_at)}</span><span className="flex gap-2"><span className="font-mono">{gbp(q.total)}</span><StatusBadge status={q.status} /></span></div>)}
              {!d.quotes.length && <p className="text-sm text-slate-400">None</p>}
            </Section>
            <Section title="Bookings">
              {d.bookings.map((b) => <div key={b.id} className="flex justify-between rounded-lg bg-slate-50 p-3 text-sm"><span>{b.service_name} · {fmtDate(b.date)} {b.slot}</span><StatusBadge status={b.status} /></div>)}
              {!d.bookings.length && <p className="text-sm text-slate-400">None</p>}
            </Section>
            {d.conversations.length > 0 && <Section title="AI receptionist summaries">{d.conversations.map((c) => <p key={c.id} className="rounded-lg bg-teal-50 p-3 text-sm text-teal-900">{c.summary || "No summary yet"}</p>)}</Section>}
            <Section title="Timeline">
              <ol className="space-y-2 border-l border-slate-200 pl-4" data-testid="lead-drawer-timeline">
                {[...(d.lead.timeline || [])].reverse().map((t, i) => <li key={i} className="text-sm"><span className="font-mono text-[10px] text-slate-400">{fmtDateTime(t.at)}</span><p>{t.text}</p></li>)}
              </ol>
            </Section>
            <Section title="Messages sent">
              {d.communications.map((c) => <div key={c.id} className="flex justify-between gap-2 text-xs"><span>{label(c.template)} · {c.channel}</span><StatusBadge status={c.status} /></div>)}
            </Section>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
