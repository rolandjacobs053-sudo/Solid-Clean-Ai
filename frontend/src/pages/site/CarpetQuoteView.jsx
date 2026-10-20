import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

const STATUS = { accepted: "Payment received - awaiting our approval. Your booking is not confirmed until we approve the appointment.", confirmed: "Your booking is confirmed. Thank you!" };

export default function CarpetQuoteView() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const t = params.get("t") || "";
  const pub = `/public/${DEFAULT_SLUG}/carpet-quotes`;
  const [q, setQ] = useState(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`${pub}/${id}`, { params: { t } }).then((r) => setQ(r.data)).catch(() => setQ("invalid")); }, [pub, id, t]);
  const accept = async () => {
    setBusy(true);
    try { const { data } = await api.post(`${pub}/${id}/accept`, { t, pay_terms_accepted: ok, origin_url: window.location.origin }); window.location.href = data.checkout_url; }
    catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  if (!q) return <div className="p-24 text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-[#023F00]" /></div>;
  if (q === "invalid") return <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="carpet-quote-invalid"><h1 className="text-3xl font-bold text-slate-900">This quote link is not valid</h1><p className="mt-3 text-slate-600">Please use the link from your email, or call us.</p></main>;
  return (
    <main className="mx-auto max-w-2xl px-4 py-14" data-testid="carpet-quote-page">
      <p className="eyebrow">Your carpet cleaning quote</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-[#023F00] sm:text-5xl">Hi {q.first_name}, here's your quote</h1>
      <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-6">
        <div className="flex items-baseline justify-between border-b border-dashed pb-4"><span className="text-slate-600">Price</span><span className="font-mono text-3xl font-bold text-[#023F00]" data-testid="carpet-quote-price">{gbp(q.price)}</span></div>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Proposed appointment</dt><dd className="text-right font-medium" data-testid="carpet-quote-when">{fmtDate(q.date)} · {q.time}</dd></div>
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Areas</dt><dd className="text-right font-medium">{q.areas.join(", ")}{q.stairs_steps ? ` · ${q.stairs_steps} steps` : ""}</dd></div>
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Address</dt><dd className="text-right font-medium">{q.address}</dd></div>
        </dl>
        {q.message && <p className="mt-4 whitespace-pre-wrap rounded-2xl bg-slate-50 p-4 text-sm text-slate-700" data-testid="carpet-quote-message">{q.message}</p>}
      </div>
      {STATUS[q.status]
        ? <p className="mt-6 flex gap-3 rounded-2xl bg-[#fbf9f1] p-5 text-[#023F00]" data-testid="carpet-quote-status"><CheckCircle2 className="h-5 w-5 shrink-0" />{STATUS[q.status]}</p>
        : <div className="mt-6 space-y-4">
          <label className="flex items-start gap-3 rounded-2xl border-2 border-[#023F00]/30 bg-[#023F00]/5 p-4 text-sm font-medium text-slate-800" data-testid="carpet-quote-terms">
            <Checkbox checked={ok} onCheckedChange={(x) => setOk(!!x)} className="mt-0.5" data-testid="carpet-quote-terms-checkbox" />
            <span>I have read and accept the <a href="/terms" target="_blank" rel="noreferrer" className="font-semibold text-[#023F00] underline">Terms and Conditions</a>, including the cancellation and refund policy.</span>
          </label>
          <Button disabled={!ok || busy} onClick={accept} className="h-12 w-full rounded-full bg-[#023F00] text-base text-white hover:bg-[#8F7E22] sm:w-auto sm:px-10" data-testid="carpet-quote-accept-btn">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Accept quote & pay {gbp(q.price)}</Button>
          <p className="text-xs text-slate-500">Secure card payment by Stripe. After payment your booking stays awaiting approval until we approve the appointment and confirm it with you.</p>
        </div>}
    </main>
  );
}
