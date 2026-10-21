import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CalendarPlus, Pencil, ShieldAlert, XCircle } from "lucide-react";
import { toast } from "sonner";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { BookingDialog } from "@/components/customers/BookingDialog";
import { CustomerForm } from "@/components/customers/CustomerForm";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fmtDate, fmtDateTime, gbp, label } from "@/lib/api";

const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Europe/London" });

const BookingList = ({ rows, onEdit, onCancel }) => (
  rows.length ? <ul className="divide-y">{rows.map((b) => (
    <li key={b.id} className="flex flex-wrap items-center gap-3 py-3 text-sm" data-testid={`customer-booking-${b.id}`}>
      <span className="w-36 font-mono text-xs">{fmtDate(b.date)} {b.slot}</span>
      <span className="min-w-[160px] flex-1">{b.service_name}<span className="block text-xs text-slate-400">{b.reference}{b.manual ? " · added manually" : " · online"}{b.assigned_name ? ` · ${b.assigned_name}` : ""}</span></span>
      <span className="font-mono">{gbp(b.total)}</span>
      <StatusBadge status={b.payment_status} testid={`customer-booking-pay-${b.id}`} />
      <StatusBadge status={b.status} testid={`customer-booking-status-${b.id}`} />
      {["confirmed", "awaiting_approval"].includes(b.status) && <>
        <Button size="sm" variant="outline" onClick={() => onEdit(b)} data-testid={`customer-booking-edit-${b.id}`}><Pencil className="mr-1 h-3.5 w-3.5" />Edit / reschedule</Button>
        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onCancel(b)} data-testid={`customer-booking-cancel-${b.id}`}><XCircle className="mr-1 h-3.5 w-3.5" />Cancel</Button>
      </>}
    </li>))}</ul> : <Empty>None.</Empty>
);

export default function CustomerDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [d, reload] = useLoad(`/admin/customers/${id}`);
  const [settings] = useLoad("/admin/settings");
  const [staff] = useLoad("/admin/staff");
  const [editing, setEditing] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [cancel, setCancel] = useState(null);
  const [erase, setErase] = useState(false);
  if (!d) return <p className="text-sm text-slate-400">Loading…</p>;
  const c = d.customer;
  const services = settings?.pricing?.services || [];
  const t = today();
  const groups = { upcoming: d.bookings.filter((b) => ["confirmed", "awaiting_approval", "pending_payment"].includes(b.status) && b.date >= t), completed: d.bookings.filter((b) => b.status === "completed" || (b.status === "confirmed" && b.date < t)), cancelled: d.bookings.filter((b) => b.status === "cancelled") };
  const save = async () => { try { await api.put(`/admin/customers/${id}`, editing); toast.success("Customer updated"); setEditing(null); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const doCancel = async () => { try { await api.patch(`/admin/bookings/${cancel.id}`, { status: "cancelled" }); toast.success("Booking cancelled"); } catch (e) { toast.error(errMsg(e)); } setCancel(null); reload(); };
  const doErase = async () => { try { await api.delete(`/admin/customers/${id}`); toast.success("Personal data erased"); nav("/admin/customers"); } catch (e) { toast.error(errMsg(e)); setErase(false); } };
  return (
    <div data-testid="customer-detail-page">
      <Link to="/admin/customers" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800" data-testid="customer-back-link"><ArrowLeft className="h-4 w-4" />All customers</Link>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-display text-3xl font-bold text-slate-900" data-testid="customer-name">{c.name}</h1><p className="text-sm text-slate-500">{label(c.contact_method || c.source)} · added {fmtDate(c.created_at)}</p></div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setEditing({ ...c, phone: c.phone || "", email: c.email || "", contact_method: c.contact_method || "phone", type: c.type || "residential", marketing_consent: !!c.marketing_consent })} data-testid="customer-edit-btn"><Pencil className="mr-2 h-4 w-4" />Edit details</Button>
          <Button onClick={() => setDialog({})} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="customer-book-btn"><CalendarPlus className="mr-2 h-4 w-4" />Book a clean</Button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Panel title="Profile">
          {editing ? <><CustomerForm v={editing} set={setEditing} services={services} /><div className="mt-4 flex gap-2"><Button onClick={save} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="customer-save-btn">Save</Button><Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button></div></> : (
            <dl className="grid gap-3 text-sm" data-testid="customer-profile">
              {[["Phone", c.phone], ["Email", c.email], ["Address", [c.address, c.postcode].filter(Boolean).join(", ")], ["Service required", services.find((s) => s.key === c.service_interest)?.name], ["Property details", c.property_details], ["Requirements", c.requirements], ["Notes / special instructions", c.notes], ["Marketing consent", c.marketing_consent ? "Yes" : "No"]].map(([k, val]) => (
                <div key={k}><dt className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{k}</dt><dd className="whitespace-pre-wrap text-slate-800">{val || "—"}</dd></div>
              ))}
            </dl>
          )}
          {user?.role === "owner" && !editing && <button onClick={() => setErase(true)} className="mt-6 flex items-center gap-1 text-xs text-slate-400 hover:text-red-600" data-testid="customer-erase-btn"><ShieldAlert className="h-3.5 w-3.5" />Erase personal data (UK GDPR request)</button>}
        </Panel>
        <Panel title={`Bookings (${d.bookings.length})`}>
          <Tabs defaultValue="upcoming">
            <TabsList className="mb-2"><TabsTrigger value="upcoming" data-testid="customer-tab-upcoming">Upcoming ({groups.upcoming.length})</TabsTrigger><TabsTrigger value="completed" data-testid="customer-tab-completed">Completed ({groups.completed.length})</TabsTrigger><TabsTrigger value="cancelled" data-testid="customer-tab-cancelled">Cancelled ({groups.cancelled.length})</TabsTrigger></TabsList>
            {Object.entries(groups).map(([k, rows]) => <TabsContent key={k} value={k}><BookingList rows={rows} onEdit={(b) => setDialog({ booking: b })} onCancel={setCancel} /></TabsContent>)}
          </Tabs>
        </Panel>
        <Panel title="Communication history" className="lg:col-span-2">
          <ul className="max-h-80 space-y-2 overflow-y-auto text-sm" data-testid="customer-comms">
            {d.timeline.map((e, i) => <li key={`t${i}`} className="flex gap-3"><span className="w-32 shrink-0 font-mono text-[11px] text-slate-400">{fmtDateTime(e.at)}</span><span>{e.text}</span></li>)}
            {d.communications.map((m) => <li key={m.id} className="flex gap-3"><span className="w-32 shrink-0 font-mono text-[11px] text-slate-400">{fmtDateTime(m.created_at)}</span><span>{label(m.channel)} · {m.subject} <StatusBadge status={m.status} /></span></li>)}
          </ul>
          {!d.timeline.length && !d.communications.length && <Empty>No history yet.</Empty>}
        </Panel>
      </div>
      <BookingDialog open={!!dialog} onClose={() => setDialog(null)} customer={c} booking={dialog?.booking} services={services} staff={staff || []} onSaved={reload} />
      <AlertDialog open={!!cancel} onOpenChange={(o) => !o && setCancel(null)}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Cancel this booking?</AlertDialogTitle><AlertDialogDescription>{cancel?.service_name} on {cancel && fmtDate(cancel.date)} {cancel?.slot}. Reminders will be stopped. For online card payments use "Cancel & refund" on the Bookings page to record a refund.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Keep booking</AlertDialogCancel><AlertDialogAction onClick={doCancel} className="bg-red-600 hover:bg-red-700" data-testid="customer-booking-cancel-confirm">Cancel booking</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={erase} onOpenChange={setErase}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Erase this customer's personal data?</AlertDialogTitle><AlertDialogDescription>Name, contact details, address, notes and messages are permanently removed. Booking amounts stay (anonymised) for your accounting records. This can't be undone.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Keep</AlertDialogCancel><AlertDialogAction onClick={doErase} className="bg-red-600 hover:bg-red-700" data-testid="customer-erase-confirm">Erase data</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
