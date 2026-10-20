import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/admin/ui";
import { RefundButton } from "@/components/admin/RefundDialog";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";

const ACCESS = { customer_present: "Customer will be present", authorised_person: "Authorised person will give access", estate_agency: "Keys collected from estate agency", other: "Other arrangement" };
const nice = (v) => (v ? String(v).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "");
const LABELS = { flat: "Flat / Apartment", good: "Well maintained", poor: "Needs extra attention", very_poor: "Very heavy soiling", part: "Part furnished", hard: "Mostly hard floors", carpet: "Mostly carpet", mixed: "Mix of carpet and hard floors", yes: "Pets live here", recent: "Pets lived here recently", no: "No pets", terms: "Terms and Conditions" };
const lab = (v) => LABELS[v] || nice(v);

export function AuthImg({ id, className }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    api.get(`/admin/bookings/photos/${id}/file`, { responseType: "blob" }).then((r) => { url = URL.createObjectURL(r.data); setSrc(url); }).catch(() => setSrc("error"));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [id]);
  if (!src) return <div className={`flex items-center justify-center bg-slate-100 ${className}`}><Loader2 className="h-4 w-4 animate-spin" /></div>;
  if (src === "error") return <div className={`flex items-center justify-center bg-slate-100 text-xs text-slate-400 ${className}`}>Unavailable</div>;
  return <a href={src} target="_blank" rel="noreferrer"><img src={src} alt="Customer upload" className={`object-cover ${className}`} data-testid="admin-photo-img" /></a>;
}

export const PhotoGrid = ({ photos, onDelete }) => (
  photos?.length
    ? <div className="grid grid-cols-3 gap-2" data-testid="admin-photo-grid">{photos.map((p) => (
      <div key={p.id} className="relative"><AuthImg id={p.id} className="aspect-square w-full rounded-xl" />
        {onDelete && <button type="button" onClick={() => onDelete(p.id)} className="absolute right-1 top-1 h-6 w-6 rounded-full bg-black/60 text-xs text-white hover:bg-red-600" aria-label="Delete photo" data-testid={`photo-delete-${p.id}`}>×</button>}</div>
    ))}</div>
    : <p className="text-sm text-slate-400" data-testid="admin-no-photos">No photos uploaded.</p>
);

const Sec = ({ title, children, testid }) => <section className="border-t border-slate-100 pt-4" data-testid={testid}><h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500">{title}</h3>{children}</section>;
const R = ({ k, v }) => (v || v === 0 ? <div className="flex justify-between gap-4 py-0.5 text-sm"><span className="text-slate-500">{k}</span><span className="text-right font-medium">{v}</span></div> : null);

function SendResults({ b, photos }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState("");
  if (user.role !== "owner" || !photos.some((p) => p.kind === "after")) return null;
  const send = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/bookings/${b.id}/results/send`);
      setLink(data.url);
      toast[data.email_status === "sent" ? "success" : "warning"](data.email_status === "sent" ? "Before & after photos emailed to the customer" : "Link created, but the email could not be sent - copy the link below");
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="rounded-xl bg-[#fbf9f1] p-3" data-testid="booking-send-results">
      <Button size="sm" className="bg-[#023F00] text-white hover:bg-[#8F7E22]" disabled={busy} onClick={send} data-testid="booking-send-results-btn">{busy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}{b.results_sent_at || link ? "Send to customer again" : "Send to customer"}</Button>
      <p className="mt-1 text-xs text-slate-500">Emails the customer a private link to their before & after photos.{b.results_sent_at && ` Last sent ${new Date(b.results_sent_at).toLocaleString("en-GB")}.`}</p>
      {link && <p className="mt-1 break-all font-mono text-xs" data-testid="booking-results-link">{link}</p>}
    </div>
  );
}

function JobPhotos({ b, photos, reload }) {
  const [busy, setBusy] = useState(false);
  const up = async (kind, files) => {
    setBusy(true);
    for (const f of files) {
      const fd = new FormData(); fd.append("file", f); fd.append("kind", kind);
      try { await api.post(`/admin/bookings/${b.id}/photos`, fd); } catch (e) { toast.error(errMsg(e)); }
    }
    setBusy(false); reload();
  };
  return <>{["before", "after"].map((kind) => (
    <Sec key={kind} title={`${kind} photos (team)`} testid={`booking-${kind}-photos`}>
      <PhotoGrid photos={photos.filter((p) => p.kind === kind)} onDelete={async (pid) => { if (!window.confirm("Delete this photo?")) return; try { await api.delete(`/admin/bookings/photos/${pid}`); reload(); } catch (e) { toast.error(errMsg(e)); } }} />
      <label className="mt-2 inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : "+"} Add {kind} photos
        <input type="file" accept="image/*,.heic,.heif" multiple hidden onChange={(e) => { const fs = [...e.target.files]; e.target.value = ""; up(kind, fs); }} data-testid={`booking-upload-${kind}-input`} />
      </label>
    </Sec>
  ))}<SendResults b={b} photos={photos} /></>;
}

function TipRequest({ b }) {
  const [sent, setSent] = useState(b.tip_request_sent_at);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/admin/bookings/${b.id}/tip-request`); setSent(new Date().toISOString()); toast.success(data.email_status === "sent" ? "Tip request emailed to the customer" : "Tip request created"); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Sec title="Tips" testid="booking-detail-tips">
      <R k="Tip added at booking" v={gbp(b.tip || 0)} />
      <R k="Tips received after the clean" v={<span data-testid="booking-detail-after-tip">{gbp(b.after_tip || 0)}</span>} />
      {sent && <p className="text-xs text-slate-500" data-testid="booking-tip-request-sent">Tip request sent {new Date(sent).toLocaleString("en-GB")}</p>}
      <Button size="sm" variant="outline" className="mt-2" disabled={busy} onClick={send} data-testid="booking-send-tip-request-btn">{busy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}{sent ? "Send tip request again" : "Send tip request"}</Button>
    </Sec>
  );
}

function Detail({ b, reload }) {
  const { user } = useAuth();
  const [photos, setPhotos] = useState(null);
  const [busy, setBusy] = useState(false);
  const loadPhotos = () => api.get(`/admin/bookings/${b.id}/photos`).then((r) => setPhotos(r.data)).catch(() => setPhotos([]));
  useEffect(() => { loadPhotos(); }, [b.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const i = b.input || {}, a = b.access || {};
  const sendBalance = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/admin/bookings/${b.id}/balance-link`); toast.success(`Balance link ${data.email_status === "sent" ? "emailed to the customer" : "created"}`); reload?.(); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="mt-4 space-y-4" data-testid="booking-detail">
      <div className="flex flex-wrap gap-2"><StatusBadge status={b.status} /><StatusBadge status={b.payment_status} /><span className="font-mono text-xs text-slate-500">ref {b.reference || "-"}</span></div>
      <Sec title="Appointment"><R k="Date" v={`${fmtDate(b.date)} · ${b.slot}`} /><R k="Assigned to" v={b.assigned_name || "Unassigned"} /></Sec>
      <Sec title="Customer" testid="booking-detail-customer"><R k="Name" v={b.customer.name} /><R k="Phone" v={<a className="underline" href={`tel:${b.customer.phone}`}>{b.customer.phone}</a>} /><R k="Email" v={<a className="underline" href={`mailto:${b.customer.email}`}>{b.customer.email}</a>} /></Sec>
      <Sec title="Property" testid="booking-detail-property">
        <R k="Address" v={[b.address || i.address, b.postcode].filter(Boolean).join(", ")} />
        <R k="Type" v={`${lab(i.property_type)} · ${i.bedrooms ?? "-"} bed · ${i.bathrooms ?? "-"} bath · ${i.living_rooms ?? "-"} living`} />
        <R k="Condition" v={lab(i.condition)} /><R k="Furnished" v={lab(i.furnished)} /><R k="Flooring" v={lab(i.flooring)} />
        <R k="Pets" v={`${lab(i.pets) || "-"}${i.pet_hair_odour ? " · significant pet hair/odour" : ""}`} />
        <R k="Additional areas" v={(i.additional_areas || []).join(", ")} />
        {i.property_notes && <p className="mt-1 rounded-lg bg-slate-50 p-2 text-sm">{i.property_notes}</p>}
      </Sec>
      <Sec title={`Customer photos (${photos ? photos.filter((p) => !p.kind).length : "…"})`} testid="booking-detail-photos">{photos ? <PhotoGrid photos={photos.filter((p) => !p.kind)} /> : <Loader2 className="h-4 w-4 animate-spin" />}</Sec>
      {photos && <JobPhotos b={b} photos={photos} reload={loadPhotos} />}
      <Sec title={`Service & price - ${b.service_name}`} testid="booking-detail-price">
        {(b.lines || b.result?.lines || []).map((l) => <R key={l.label} k={l.label} v={gbp(l.amount)} />)}
        <R k="Total" v={gbp(b.total)} />
        {b.tip > 0 && <R k="Tip for the team" v={<span data-testid="booking-detail-tip">{gbp(b.tip)}</span>} />}
        {b.deposit_amount != null && b.deposit_amount < b.total && <><R k="Deposit (50%)" v={gbp(b.deposit_amount)} /><R k="Balance due" v={gbp(b.balance_due)} /></>}
        {user.role === "owner" && b.payment_status === "deposit_paid" && b.balance_due > 0 && <Button size="sm" className="mt-2 bg-[#023F00] text-white hover:bg-[#8F7E22]" disabled={busy} onClick={sendBalance} data-testid="booking-send-balance-btn">Email balance payment link</Button>}
        <div className="mt-2"><RefundButton b={b} onDone={reload} /></div>
      </Sec>
      {user.role === "owner" && b.status === "completed" && <TipRequest b={b} />}
      {b.refund && (
        <Sec title="Cancellation & refund" testid="booking-detail-refund">
          <R k="Refund to issue in Stripe" v={<span className="font-mono" data-testid="booking-detail-refund-amount">{gbp(b.refund.amount)}</span>} />
          <R k="Rule applied" v={`${b.refund.rule_percent}% · ${b.refund.notice_hours} h notice (suggested ${gbp(b.refund.suggested)})`} />
          {b.refund.note && <p className="mt-1 rounded-lg bg-slate-50 p-2 text-sm">{b.refund.note}</p>}
          <p className="mt-1 text-xs text-slate-400">Recorded {new Date(b.refund.recorded_at).toLocaleString("en-GB")}</p>
        </Sec>
      )}
      <Sec title="Access & keys" testid="booking-detail-access">
        <R k="Method" v={ACCESS[a.method] || "-"} />
        <R k="Person" v={a.method === "authorised_person" && `${a.person_name} · ${a.person_phone}`} />
        <R k="Agency" v={a.method === "estate_agency" && `${a.agency_name}, ${a.agency_address}`} />
        {a.agency_instructions && <p className="rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{a.agency_instructions}</p>}
        {(a.notes || (!b.access && b.access_notes)) && <p className="mt-1 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">{a.notes || b.access_notes}</p>}
      </Sec>
      <Sec title="Booking terms accepted" testid="booking-detail-terms">
        {Object.entries(b.accepted_policies || {}).map(([k, v]) => <R key={k} k={<a className="underline" href={`/policies#${k}`} target="_blank" rel="noreferrer">{lab(k)}</a>} v={`version ${v}`} />)}
        {!Object.keys(b.accepted_policies || {}).length && <p className="text-sm text-slate-400">No terms were required when this booking was made.</p>}
        <p className="mt-1 text-xs text-slate-400">Recorded {b.created_at ? new Date(b.created_at).toLocaleString("en-GB") : ""}</p>
      </Sec>
    </div>
  );
}

export function BookingDetail({ b, onClose, reload }) {
  return (
    <Sheet open={!!b} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg" data-testid="booking-detail-sheet">
        <SheetHeader><SheetTitle>{b?.service_name}</SheetTitle></SheetHeader>
        {b && <Detail b={b} reload={reload} />}
      </SheetContent>
    </Sheet>
  );
}
