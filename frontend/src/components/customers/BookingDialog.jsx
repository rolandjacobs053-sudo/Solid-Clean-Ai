import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";

const F = ({ label: l, children, wide }) => <div className={`space-y-1 ${wide ? "sm:col-span-2" : ""}`}><Label className="text-xs text-slate-600">{l}</Label>{children}</div>;
const blank = (c) => ({ service: c?.service_interest || "regular", date: "", slot: "09:00", duration_hours: 3, price: "", payment_status: "due", amount_paid: "", payment_method: "", address: c?.address || "", postcode: c?.postcode || "", requirements: c?.requirements || "", special_instructions: c?.notes || "", assigned_to: "", send_confirmation: false });

export const BookingDialog = ({ open, onClose, customer, booking, services, staff, onSaved }) => {
  const edit = !!booking;
  const [v, setV] = useState(blank(customer));
  const [conflict, setConflict] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setConflict(null);
    setV(edit ? { ...blank(customer), service: booking.service, date: booking.date, slot: booking.slot, duration_hours: booking.duration_hours || 3, price: booking.total, payment_status: booking.payment_status, amount_paid: booking.deposit_amount || "", requirements: booking.requirements || "", special_instructions: booking.special_instructions || booking.access_notes || "", send_confirmation: false } : blank(customer));
  }, [open, booking, customer, edit]);
  const bind = (k) => ({ value: v[k] ?? "", onChange: (e) => setV({ ...v, [k]: e.target.value }), "data-testid": `booking-${k.replace(/_/g, "-")}-input` });
  const manual = !edit || booking.manual;

  const save = async (allow = false) => {
    if (!v.date || !v.slot || v.price === "") return toast.error("Choose a date, start time and price");
    setBusy(true);
    try {
      if (edit) {
        const body = { date: v.date, slot: v.slot, duration_hours: Number(v.duration_hours), requirements: v.requirements, special_instructions: v.special_instructions, notify_customer: v.send_confirmation, allow_conflict: allow };
        if (manual) Object.assign(body, { price: Number(v.price), payment_status: v.payment_status, amount_paid: Number(v.amount_paid) || 0 });
        await api.patch(`/admin/customers/bookings/${booking.id}`, body);
        toast.success("Booking updated");
      } else {
        const { data } = await api.post(`/admin/customers/${customer.id}/bookings`, { ...v, price: Number(v.price), duration_hours: Number(v.duration_hours), amount_paid: Number(v.amount_paid) || 0, assigned_to: v.assigned_to || null, allow_conflict: allow });
        toast.success(`Booking ${data.reference} created`);
      }
      onSaved();
      onClose();
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (e?.response?.status === 409 && d?.conflicts) setConflict(d); else toast.error(errMsg(e));
    }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto" data-testid="booking-dialog">
        <DialogHeader><DialogTitle>{edit ? `Edit / reschedule ${booking.reference || ""}` : `Book a clean for ${customer?.name}`}</DialogTitle></DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <F label="Service">
            <Select value={v.service} onValueChange={(x) => setV({ ...v, service: x })} disabled={edit}>
              <SelectTrigger data-testid="booking-service-select"><SelectValue /></SelectTrigger>
              <SelectContent>{services.map((s) => <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          </F>
          <F label="Date"><Input type="date" {...bind("date")} /></F>
          <F label="Start time"><Input type="time" {...bind("slot")} /></F>
          <F label="Duration (hours)"><Input type="number" min="0.5" step="0.5" {...bind("duration_hours")} /></F>
          <F label="Price (£)"><Input type="number" min="0" step="0.01" disabled={!manual} {...bind("price")} /></F>
          <F label="Payment status">
            <Select value={v.payment_status} onValueChange={(x) => setV({ ...v, payment_status: x })} disabled={!manual}>
              <SelectTrigger data-testid="booking-payment-status-select"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="due">Not paid yet</SelectItem><SelectItem value="deposit_paid">Part paid</SelectItem><SelectItem value="paid">Paid in full</SelectItem></SelectContent>
            </Select>
          </F>
          {v.payment_status === "deposit_paid" && manual && <F label="Amount already paid (£)"><Input type="number" min="0" step="0.01" {...bind("amount_paid")} /></F>}
          {!edit && <F label="Payment method (cash, bank transfer, card…)"><Input {...bind("payment_method")} /></F>}
          {!edit && (
            <F label="Assign cleaner">
              <Select value={v.assigned_to || "none"} onValueChange={(x) => setV({ ...v, assigned_to: x === "none" ? "" : x })}>
                <SelectTrigger data-testid="booking-assign-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="none">Unassigned</SelectItem>{staff.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
              </Select>
            </F>
          )}
          {!edit && <F label="Address" wide><Input {...bind("address")} /></F>}
          {!edit && <F label="Postcode"><Input {...bind("postcode")} /></F>}
          <F label="Additional requirements" wide><Textarea rows={2} {...bind("requirements")} /></F>
          <F label="Special instructions (access, keys, parking)" wide><Textarea rows={2} {...bind("special_instructions")} /></F>
          {!manual && <p className="text-xs text-amber-700 sm:col-span-2">Online card booking: price and payment are managed by Stripe. Use the refund or balance link tools on Bookings for money changes.</p>}
          <label className="flex items-center gap-2 text-sm sm:col-span-2"><Checkbox checked={v.send_confirmation} onCheckedChange={(x) => setV({ ...v, send_confirmation: !!x })} data-testid="booking-notify-checkbox" />{edit ? "Email the customer the updated booking" : "Email the customer a booking confirmation and reminder"}</label>
        </div>
        {conflict && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="booking-conflict-alert">
            <p className="flex items-center gap-2 font-semibold text-amber-900"><AlertTriangle className="h-4 w-4" />{conflict.message}</p>
            <ul className="mt-2 space-y-1 text-xs text-amber-900">{conflict.conflicts.map((c) => <li key={c.id}>{c.slot} · {c.service} · {c.customer}{c.assigned_name ? ` · ${c.assigned_name}` : ""}{c.double_booking ? " (double booking)" : ""}</li>)}</ul>
            {conflict.can_override && <Button size="sm" variant="outline" className="mt-3" onClick={() => save(true)} data-testid="booking-override-btn">Book anyway</Button>}
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button onClick={() => save(false)} disabled={busy} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="booking-save-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{edit ? "Save changes" : "Create booking"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
