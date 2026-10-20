import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, Star } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg, fmtDate } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

export default function FeedbackPage() {
  const { bookingId } = useParams();
  const [params] = useSearchParams();
  const t = params.get("t") || "";
  const url = `/public/${DEFAULT_SLUG}/feedback/${bookingId}`;
  const [info, setInfo] = useState(null);
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  useEffect(() => { api.get(url, { params: { t } }).then((r) => { setInfo(r.data); setName(r.data.suggested_name); }).catch(() => setInfo("invalid")); }, [url, t]);
  const submit = async () => {
    setBusy(true);
    try { await api.post(url, { t, rating, text, display_name: name, publish_consent: consent }); setSent(true); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  if (!info) return <div className="p-24 text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-[#023F00]" /></div>;
  if (info === "invalid") return <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="feedback-invalid"><h1 className="text-3xl font-bold text-slate-900">This link is not valid</h1><p className="mt-3 text-slate-600">Please use the link from your email.</p></main>;
  if (sent || info.done) return (
    <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="feedback-thanks">
      <CheckCircle2 className="mx-auto h-12 w-12 text-[#023F00]" /><h1 className="mt-5 text-3xl font-bold text-[#023F00]">Thank you for your feedback</h1>
      <p className="mt-3 text-slate-600">It really helps us improve.</p>
      {info.google_link && <a href={info.google_link} target="_blank" rel="noreferrer" className="mt-6 inline-block rounded-full border-2 border-[#8F7E22] px-6 py-3 text-sm font-semibold text-[#023F00]" data-testid="feedback-google-link">Would you also share it on Google?</a>}
    </main>
  );
  return (
    <main className="mx-auto max-w-xl px-4 py-14 sm:py-20" data-testid="feedback-page">
      <p className="eyebrow">How did we do?</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-[#023F00]">Rate your clean, {info.first_name}</h1>
      <p className="mt-3 text-slate-600">Your {info.service_name} on <b>{fmtDate(info.date)}</b>. Please be honest - good or bad, we read every review.</p>
      <div className="mt-8 flex gap-2" data-testid="feedback-stars">
        {[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" onClick={() => setRating(n)} aria-label={`${n} stars`} data-testid={`feedback-star-${n}`}><Star className={`h-10 w-10 transition-transform hover:scale-110 ${n <= rating ? "fill-amber-400 text-amber-400" : "text-slate-300"}`} /></button>)}
      </div>
      <div className="mt-6 space-y-5">
        <div><Label htmlFor="fb-text">Your comments</Label><Textarea id="fb-text" rows={5} value={text} onChange={(e) => setText(e.target.value)} className="mt-2 rounded-xl" placeholder="What did you like? What could we do better?" data-testid="feedback-text" /></div>
        <div><Label htmlFor="fb-name">Name shown with your review</Label><Input id="fb-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-2 h-11 max-w-xs rounded-xl" data-testid="feedback-name" /></div>
        <label className="flex items-start gap-3 text-sm text-slate-700"><Checkbox checked={consent} onCheckedChange={(c) => setConsent(!!c)} className="mt-0.5" data-testid="feedback-consent" />Solid Clean Ltd may show my rating, comments and name on its website.</label>
        <Button disabled={!rating || !name.trim() || busy} onClick={submit} className="h-12 rounded-full bg-[#023F00] px-8 text-white hover:bg-[#8F7E22]" data-testid="feedback-submit-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Send feedback</Button>
      </div>
    </main>
  );
}
