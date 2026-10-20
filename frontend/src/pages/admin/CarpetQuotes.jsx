import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { PhotoGrid } from "@/components/admin/BookingDetail";
import { CARPET_AREAS } from "@/pages/site/CarpetPage";
import { api, errMsg, fmtDate, fmtDateTime, gbp } from "@/lib/api";

const AREA = Object.fromEntries(CARPET_AREAS.map(([k, n]) => [k, n]));
const ANS = { visible_stains: "Visible stains", heavily_soiled: "Heavily soiled", concerns: "Marks / areas of concern", pets: "Pets in the property", pet_hair: "Pet hair", pet_urine: "Pet urine stains", pet_odour: "Pet odours", stain_treatment: "Stain treatment requested", odour_treatment: "Odour treatment requested" };
const R = ({ k, v }) => (v ? <div className="flex justify-between gap-4 py-0.5 text-sm"><span className="text-slate-500">{k}</span><span className="text-right font-medium">{String(v).replace(/_/g, " ")}</span></div> : null);
const Sec = ({ title, children, testid }) => <section className="border-t border-slate-100 pt-4" data-testid={testid}><h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500">{title}</h3>{children}</section>;

function Actions({ q, reload }) {
  const [f, setF] = useState({ price: q.quote?.price ?? 100, date: q.quote?.date || q.preferred_date, time: q.quote?.time || q.preferred_time, message: q.quote?.message || "" });
  const call = async (path, body, msg) => { try { await api.post(`/admin/carpet-quotes/${q.id}/${path}`, body); toast.success(msg); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (["confirmed", "declined"].includes(q.status)) return null;
  return (
    <Sec title="Review & respond" testid="carpet-admin-actions">
      {["awaiting_review", "quoted"].includes(q.status) && <>
        <div className="grid grid-cols-3 gap-2">
          <div><Label>Price (£)</Label><Input type="number" min="1" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid="carpet-admin-price" /></div>
          <div><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="carpet-admin-date" /></div>
          <div><Label>Time</Label><Input value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} data-testid="carpet-admin-time" /></div>
        </div>
        <Label className="mt-2 block">Message / service details for the customer</Label>
        <Textarea value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} data-testid="carpet-admin-message" />
        <Button size="sm" className="mt-3 bg-[#023F00] text-white hover:bg-[#8F7E22]" onClick={() => call("quote", { ...f, price: Number(f.price) }, "Quote emailed to the customer")} data-testid="carpet-send-quote-btn">{q.status === "quoted" ? "Resend updated quote" : "Send quote"}</Button>
      </>}
      {q.status === "accepted" && <Button size="sm" className="bg-[#023F00] text-white hover:bg-[#8F7E22]" onClick={() => call("approve", {}, "Booking approved and confirmed")} data-testid="carpet-approve-btn">Approve & confirm booking</Button>}
      <Button size="sm" variant="ghost" className="ml-2 mt-3 text-red-700" onClick={() => call("decline", { message: "" }, q.status === "accepted" ? "Declined - full refund recorded, issue it in Stripe" : "Request declined")} data-testid="carpet-decline-btn">Decline</Button>
    </Sec>
  );
}

function Detail({ id, reload }) {
  const [d, setD] = useState(null);
  const load = () => api.get(`/admin/carpet-quotes/${id}`).then((r) => setD(r.data));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return <p className="mt-4 font-mono text-sm">Loading…</p>;
  const q = d.quote;
  return (
    <div className="mt-4 space-y-4" data-testid="carpet-quote-detail">
      <StatusBadge status={q.status} />
      <Sec title="Requested time (not confirmed)"><R k="Preferred" v={`${fmtDate(q.preferred_date)} ${q.preferred_time}`} />{q.quote && <R k="Quoted" v={`${gbp(q.quote.price)} · ${fmtDate(q.quote.date)} ${q.quote.time}`} />}</Sec>
      <Sec title="Customer"><R k="Name" v={q.contact.name} /><R k="Phone" v={q.contact.phone} /><R k="Email" v={q.contact.email} /><R k="Address" v={`${q.address}, ${q.postcode}`} /></Sec>
      <Sec title="Areas" testid="carpet-detail-areas">{Object.entries(q.areas).map(([k, v]) => <R key={k} k={AREA[k] || k} v={`× ${v}`} />)}
        {q.areas.stairs && <><R k="Carpeted steps" v={q.stairs_steps} /><R k="Landing too" v={q.stairs_landing} /></>}<R k="Other areas" v={q.other_areas} /></Sec>
      <Sec title="Condition, pets & treatments" testid="carpet-detail-answers">{Object.entries(q.answers || {}).map(([k, v]) => <R key={k} k={ANS[k] || k} v={v} />)}{q.notes && <p className="mt-1 rounded-lg bg-slate-50 p-2 text-sm">{q.notes}</p>}</Sec>
      <Sec title={`Photos (${d.photos.length})`} testid="carpet-detail-photos"><PhotoGrid photos={d.photos} /></Sec>
      <Actions q={q} reload={() => { load(); reload(); }} />
      <Sec title="History">{(q.history || []).map((h, i) => <p key={i} className="text-xs text-slate-600">{fmtDateTime(h.at)} · {h.text}</p>)}</Sec>
    </div>
  );
}

export default function CarpetQuotes() {
  const [rows, reload] = useLoad("/admin/carpet-quotes");
  const [sel, setSel] = useState(null);
  return (
    <div data-testid="admin-carpet-quotes-page">
      <PageHeader eyebrow="Carpet cleaning" title="Carpet quote requests" desc="Review each request and its photos, send a quote, then approve the appointment once the customer has accepted and paid. Nothing is confirmed until you approve it." />
      <div className="space-y-2">
        {rows?.map((q) => (
          <button key={q.id} onClick={() => setSel(q.id)} className="flex w-full flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-left hover:border-[#8F7E22]" data-testid="carpet-quote-row">
            <span><b>{q.contact.name}</b> · {Object.keys(q.areas).map((k) => AREA[k]).join(", ")}<span className="block text-xs text-slate-500">{q.postcode} · requested {fmtDateTime(q.created_at)}</span></span>
            <span className="flex items-center gap-3 font-mono text-xs">{fmtDate(q.preferred_date)} {q.preferred_time}<StatusBadge status={q.status} /></span>
          </button>
        ))}
        {rows?.length === 0 && <Empty>No carpet cleaning requests yet.</Empty>}
      </div>
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg" data-testid="carpet-quote-sheet"><SheetHeader><SheetTitle>Carpet cleaning request</SheetTitle></SheetHeader>{sel && <Detail id={sel} reload={reload} />}</SheetContent>
      </Sheet>
    </div>
  );
}
