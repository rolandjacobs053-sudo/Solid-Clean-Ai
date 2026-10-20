import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, fmtDate, gbp } from "@/lib/api";
import { useTenant } from "@/lib/tenant";

export default function PaymentResult() {
  const { result } = useParams();
  const [params] = useSearchParams();
  const { base, pub } = useTenant();
  const [state, setState] = useState({ status: "checking" });

  useEffect(() => {
    if (result === "cancel") {
      const bid = params.get("booking_id");
      if (bid) api.post(`${pub}/bookings/${bid}/release`).catch(() => {});
      setState({ status: "cancelled" });
      return;
    }
    const sid = params.get("session_id");
    let tries = 0;
    const poll = async () => {
      try {
        const { data } = await api.get(`/payments/status/${sid}`);
        if (data.payment_status === "paid") return setState({ status: "paid", booking: data.booking, amount: data.amount, kind: data.kind });
      } catch { /* retry */ }
      if (++tries < 10) setTimeout(poll, 2000);
      else setState({ status: "pending" });
    };
    poll();
  }, [result, params, pub]);

  const { status, booking, amount, kind } = state;
  return (
    <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="payment-result-page">
      {status === "checking" && <><Loader2 className="mx-auto h-10 w-10 animate-spin text-teal-600" /><p className="mt-4 text-slate-600" data-testid="payment-status-checking">Confirming your payment…</p></>}
      {status === "paid" && (
        <div data-testid="payment-status-paid">
          <CheckCircle2 className="mx-auto h-14 w-14 text-teal-600" />
          <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-slate-900">{kind === "tip" ? "Thank you for your tip!" : kind === "carpet" ? "Payment received - awaiting approval" : kind === "balance" ? "Balance paid - thank you" : "Booking confirmed"}</h1>
          <p className="mt-4 text-slate-600">{booking.service_name} on <b>{fmtDate(booking.date)}</b> at <b>{booking.slot}</b>.</p>
          <p className="mt-2 font-mono text-2xl font-bold text-teal-700">{gbp(amount ?? booking.total)} {kind === "deposit" ? "deposit paid" : kind === "tip" ? "tip paid" : "paid"}</p>
          {kind === "deposit" && <p className="mt-2 text-sm text-slate-600">The remaining {gbp(booking.total - amount)} is due immediately after the clean.</p>}
          {booking.recurring && <p className="mt-2 text-sm text-slate-600" data-testid="payment-recurring-note">Your regular {(booking.frequency || "").toLowerCase()} is set up. Each next visit is charged automatically to your saved card 2 days before.</p>}
          <p className="mt-4 text-sm text-slate-500">{kind === "tip" ? "We'll pass your thanks on to the team." : kind === "carpet" ? "Your booking is not confirmed until we approve the appointment. We'll be in touch shortly to confirm." : "A confirmation is on its way, and we'll send a reminder the day before."}</p>
        </div>
      )}
      {status === "pending" && <p className="text-slate-600" data-testid="payment-status-pending">We're still waiting for confirmation from the payment provider. You'll receive an email once it completes.</p>}
      {status === "cancelled" && (
        <div data-testid="payment-status-cancelled">
          <XCircle className="mx-auto h-14 w-14 text-slate-400" />
          <h1 className="mt-6 text-3xl font-bold text-slate-900">Payment cancelled</h1>
          <p className="mt-3 text-slate-600">No payment was taken and your slot was released.</p>
        </div>
      )}
      <Button asChild className="mt-10 rounded-full bg-slate-900 hover:bg-teal-700 hover:text-white" data-testid="payment-back-home-btn"><Link to={["tip", "carpet"].includes(kind) ? `${base}/` : `${base}/quote`}>{["tip", "carpet"].includes(kind) ? "Back to home" : "Back to booking"}</Link></Button>
    </main>
  );
}
