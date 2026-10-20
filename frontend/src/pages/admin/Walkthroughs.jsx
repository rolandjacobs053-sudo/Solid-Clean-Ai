import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { PhotoGrid } from "@/components/admin/BookingDetail";
import { api, errMsg, fmtDate, fmtDateTime } from "@/lib/api";

const nice = (v) => (Array.isArray(v) ? v.join(", ") : v === true ? "Yes" : String(v ?? "").replace(/_/g, " "));
const R = ({ k, v }) => (v ? <div className="flex justify-between gap-4 py-0.5 text-sm"><span className="text-slate-500">{k}</span><span className="text-right font-medium">{nice(v)}</span></div> : null);
const Sec = ({ title, children, testid }) => <section className="border-t border-slate-100 pt-4" data-testid={testid}><h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500">{title}</h3>{children}</section>;

function Actions({ w, reload }) {
  const [f, setF] = useState({ confirmed_date: w.visit.preferred_date, confirmed_time: w.visit.preferred_time, message: "" });
  const send = async (status) => {
    try { await api.patch(`/admin/walkthroughs/${w.id}`, { status, ...f }); toast.success(status === "confirmed" ? "Visit confirmed - customer emailed" : status === "alternative_proposed" ? "Alternative sent to customer" : "Status updated"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Sec title="Review & respond" testid="walkthrough-actions">
      <div className="grid grid-cols-2 gap-2">
        <div><Label>Date</Label><Input type="date" value={f.confirmed_date} onChange={(e) => setF({ ...f, confirmed_date: e.target.value })} data-testid="wt-admin-date" /></div>
        <div><Label>Time</Label><Input value={f.confirmed_time} onChange={(e) => setF({ ...f, confirmed_time: e.target.value })} data-testid="wt-admin-time" /></div>
      </div>
      <Label className="mt-2 block">Message to customer (required to propose another time)</Label>
      <Textarea value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} data-testid="wt-admin-message" />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" className="bg-[#023F00] text-white hover:bg-[#8F7E22]" onClick={() => send("confirmed")} data-testid="wt-confirm-btn">Confirm visit</Button>
        <Button size="sm" variant="outline" onClick={() => send("alternative_proposed")} data-testid="wt-propose-btn">Propose another time</Button>
        <Button size="sm" variant="outline" onClick={() => send("completed")} data-testid="wt-complete-btn">Mark visited</Button>
        <Button size="sm" variant="ghost" onClick={() => send("declined")} data-testid="wt-decline-btn">Decline</Button>
      </div>
    </Sec>
  );
}

function Detail({ id, reload }) {
  const [d, setD] = useState(null);
  const load = () => api.get(`/admin/walkthroughs/${id}`).then((r) => setD(r.data));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return <p className="mt-4 font-mono text-sm">Loading…</p>;
  const w = d.walkthrough, s = w.schedule, v = w.visit;
  return (
    <div className="mt-4 space-y-4" data-testid="walkthrough-detail">
      <div className="flex flex-wrap items-center gap-2"><StatusBadge status={w.status} /><span className="text-xs text-slate-500">{w.availability_note}</span></div>
      <Sec title="Requested visit"><R k="Preferred" v={`${fmtDate(v.preferred_date)} ${v.preferred_time}`} /><R k="Alternative" v={v.alt_date && `${fmtDate(v.alt_date)} ${v.alt_time}`} /><R k="Access for visit" v={v.access_info} />{w.confirmed_date && <R k="Confirmed" v={`${fmtDate(w.confirmed_date)} ${w.confirmed_time}`} />}</Sec>
      <Sec title="Business & contact"><R k="Business" v={w.business_name} /><R k="Premises type" v={w.establishment_name} /><R k="Contact" v={w.contact.name} />
        <R k="Phone" v={w.contact.phone} /><R k="Email" v={w.contact.email} /><R k="Address" v={`${w.address}, ${w.postcode}`} />
        <div className="mt-2 flex gap-2"><a className="text-xs underline" href={`tel:${w.contact.phone}`}>Call</a><a className="text-xs underline" href={`mailto:${w.contact.email}`}>Email</a></div></Sec>
      <Sec title="Premises answers" testid="walkthrough-answers">{Object.entries(w.details || {}).map(([k, x]) => <R key={k} k={nice(k)} v={x} />)}</Sec>
      <Sec title="Cleaning requirements"><R k="Type" v={s.kind} /><R k="Frequency" v={s.frequency} /><R k="Days" v={s.days} /><R k="Time" v={s.time} /><R k="Preferred start" v={s.start_date && fmtDate(s.start_date)} /><R k="Notes" v={s.notes} /></Sec>
      <Sec title={`Photos (${d.photos.length})`} testid="walkthrough-photos"><PhotoGrid photos={d.photos} /></Sec>
      <Actions w={w} reload={() => { load(); reload(); }} />
      <Sec title="History">{(w.history || []).map((h, i) => <p key={i} className="text-xs text-slate-600">{fmtDateTime(h.at)} · {h.text}</p>)}</Sec>
    </div>
  );
}

export default function Walkthroughs() {
  const [rows, reload] = useLoad("/admin/walkthroughs");
  const [sel, setSel] = useState(null);
  return (
    <div data-testid="admin-walkthroughs-page">
      <PageHeader eyebrow="Commercial" title="Site walkthrough requests" desc="Free commercial site walkthrough requests from the website. Requested times are not confirmed until you confirm them here." />
      <div className="space-y-2">
        {rows?.map((w) => (
          <button key={w.id} onClick={() => setSel(w.id)} className="flex w-full flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-left hover:border-[#8F7E22]" data-testid="walkthrough-row">
            <span><b>{w.business_name}</b> · {w.establishment_name}<span className="block text-xs text-slate-500">{w.contact.name} · {w.postcode} · requested {fmtDateTime(w.created_at)}</span></span>
            <span className="flex items-center gap-3 font-mono text-xs">{fmtDate(w.visit.preferred_date)} {w.visit.preferred_time}<StatusBadge status={w.status} /></span>
          </button>
        ))}
        {rows?.length === 0 && <Empty>No walkthrough requests yet.</Empty>}
      </div>
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg" data-testid="walkthrough-sheet"><SheetHeader><SheetTitle>Site walkthrough request</SheetTitle></SheetHeader>{sel && <Detail id={sel} reload={reload} />}</SheetContent>
      </Sheet>
    </div>
  );
}
