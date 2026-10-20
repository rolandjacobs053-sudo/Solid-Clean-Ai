import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Heart, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";
import { useTenant } from "@/lib/tenant";

const AMOUNTS = [5, 10, 15, 20];

export default function TipPage() {
  const { bookingId } = useParams();
  const [params] = useSearchParams();
  const { base, pub } = useTenant();
  const t = params.get("t") || "";
  const [info, setInfo] = useState(null);
  const [amount, setAmount] = useState(10);
  const [custom, setCustom] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get(`${pub}/tips/${bookingId}`, { params: { t } }).then((r) => setInfo(r.data)).catch(() => setInfo("invalid"));
  }, [pub, bookingId, t]);
  const pay = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`${pub}/tips/${bookingId}`, { t, amount, origin_url: `${window.location.origin}${base}` });
      window.location.href = data.checkout_url;
    } catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  if (!info) return <div className="p-24 text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-[#023F00]" /></div>;
  if (info === "invalid") return <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="tip-invalid"><h1 className="text-3xl font-bold text-slate-900">This tip link is not valid</h1><p className="mt-3 text-slate-600">Please use the link from your email, or contact us.</p></main>;
  const pill = (on) => `rounded-full border-2 px-5 py-2 font-mono text-lg font-semibold transition-colors ${on ? "border-[#023F00] bg-[#023F00] text-white" : "border-slate-200 bg-white text-slate-800 hover:border-[#8F7E22]"}`;
  return (
    <main className="mx-auto max-w-xl px-4 py-16 sm:py-24" data-testid="tip-page">
      <Heart className="h-10 w-10 text-[#8F7E22]" />
      <p className="eyebrow mt-6">Thank you, {info.first_name}</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-[#023F00] sm:text-5xl">Leave a tip for your cleaning team</h1>
      <p className="mt-4 text-slate-600">For your {info.service_name} on <b>{fmtDate(info.date)}</b>{info.cleaner ? <> with <b>{info.cleaner}</b></> : null}. Tipping is entirely optional.</p>
      {info.tips_received > 0 && <p className="mt-3 rounded-xl bg-[#023F00]/5 p-3 text-sm text-[#023F00]" data-testid="tip-already">You've already left {gbp(info.tips_received)} - thank you!</p>}
      <div className="mt-8 flex flex-wrap gap-3">
        {AMOUNTS.map((a) => <button key={a} type="button" className={pill(!custom && amount === a)} onClick={() => { setCustom(false); setAmount(a); }} data-testid={`tip-amount-${a}`}>{gbp(a)}</button>)}
      </div>
      <div className="mt-4 flex items-center gap-2"><span className="text-sm text-slate-500">Or enter an amount (£)</span>
        <Input type="number" min="1" max="500" value={amount || ""} onChange={(e) => { setCustom(true); setAmount(Math.min(500, Math.max(0, Number(e.target.value) || 0))); }} className="w-32 font-mono" data-testid="tip-custom-amount" /><span className="text-xs text-slate-400">max £500</span></div>
      <Button disabled={busy || amount < 1} onClick={pay} className="mt-8 h-12 rounded-full bg-[#023F00] px-8 text-base text-white hover:bg-[#8F7E22]" data-testid="tip-pay-btn">
        {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Pay {gbp(amount || 0)} tip securely
      </Button>
      <p className="mt-3 text-xs text-slate-500">Card payment processed securely by Stripe.</p>
    </main>
  );
}
