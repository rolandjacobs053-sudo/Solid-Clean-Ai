import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, gbp } from "@/lib/api";

const RULES = [[100, "7+ days' notice", "Full refund"], [50, "48 hours to 7 days' notice", "50% refund"], [0, "Less than 48 hours' notice", "No refund"]];

const Rules = ({ pct }) => (
  <ul className="space-y-1 text-sm" data-testid="refund-rules">
    {RULES.map(([p, k, v]) => (
      <li key={p} className={`flex justify-between rounded-lg px-3 py-1.5 ${p === pct ? "bg-[#023F00] font-semibold text-white" : "bg-slate-50 text-slate-600"}`} data-testid={`refund-rule-${p}`}><span>{k}</span><span>{v}</span></li>
    ))}
  </ul>
);

export function RefundButton({ b, onDone, size = "sm" }) {
  const { user } = useAuth();
  const [q, setQ] = useState(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (user?.role !== "owner" || b.status !== "confirmed" || !["paid", "deposit_paid"].includes(b.payment_status)) return null;
  const start = async () => {
    try { const { data } = await api.get(`/admin/bookings/${b.id}/refund-quote`); setQ(data); setAmount(String(data.suggested)); setNote(""); } catch (e) { toast.error(errMsg(e)); }
  };
  const value = Number(amount);
  const valid = amount !== "" && value >= 0 && q && value <= q.paid;
  const confirm = async () => {
    setBusy(true);
    try {
      await api.post(`/admin/bookings/${b.id}/cancel-refund`, { amount: value, note });
      toast.success(value > 0 ? `Booking cancelled. Refund of ${gbp(value)} recorded - issue it in Stripe.` : "Booking cancelled. No refund due.", { duration: 8000 });
      setQ(null); onDone?.();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <span onClick={(e) => e.stopPropagation()}>
      <Button size={size} variant="outline" className="border-red-200 text-red-700 hover:bg-red-50" onClick={start} data-testid={`booking-refund-btn-${b.id}`}>Cancel & refund</Button>
      <Dialog open={!!q} onOpenChange={(o) => !o && setQ(null)}>
        <DialogContent className="max-w-md" data-testid="refund-dialog">
          <DialogHeader>
            <DialogTitle>Cancel & refund</DialogTitle>
            <DialogDescription>{b.customer?.name} · ref {b.reference || "-"}</DialogDescription>
          </DialogHeader>
          {q && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600" data-testid="refund-notice">Notice given: <b>{q.notice_hours >= 48 ? `${Math.floor(q.notice_hours / 24)} days ${Math.round(q.notice_hours % 24)} h` : `${q.notice_hours} hours`}</b> before the appointment.</p>
              <Rules pct={q.rule_percent} />
              <div className="rounded-xl border border-slate-200 p-3 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Paid for the clean</span><span className="font-mono">{gbp(q.service_paid)}</span></div>
                {q.tip > 0 && <div className="flex justify-between"><span className="text-slate-500">Tip (refunded in full)</span><span className="font-mono">{gbp(q.tip)}</span></div>}
                <div className="mt-1 flex justify-between border-t border-dashed pt-1 font-semibold"><span>Suggested refund ({q.rule_percent}%)</span><span className="font-mono" data-testid="refund-suggested">{gbp(q.suggested)}</span></div>
              </div>
              <div><Label className="text-xs">Refund amount (£) - change it for goodwill if you like</Label><Input type="number" min="0" max={q.paid} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="mt-1 font-mono" data-testid="refund-amount-input" />
                {!valid && <p className="mt-1 text-xs text-red-600" data-testid="refund-amount-error">Enter an amount between £0 and {gbp(q.paid)}.</p>}</div>
              <div><Label className="text-xs">Note (optional, internal)</Label><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="mt-1" data-testid="refund-note-input" /></div>
              <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900">This cancels the booking and emails the customer. No money is sent automatically - issue the refund yourself in Stripe.</p>
              <Button disabled={!valid || busy} onClick={confirm} className="w-full bg-red-700 text-white hover:bg-red-800" data-testid="refund-confirm-btn">
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Cancel booking & record {valid ? gbp(value) : ""} refund
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </span>
  );
}
