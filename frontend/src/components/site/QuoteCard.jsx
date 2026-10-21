import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { gbp } from "@/lib/api";
import { useTenant } from "@/lib/tenant";

export function QuoteCard({ quoteId, quoteToken, result }) {
  const navigate = useNavigate();
  const { base } = useTenant();
  const ok = result.status === "ok";
  return (
    <div className="rounded-2xl border border-teal-200 bg-white p-4 shadow-sm" data-testid="chat-quote-card">
      <p className="eyebrow">Quote · from approved price list</p>
      <p className="mt-1 font-display text-base font-semibold text-slate-900">{result.service_name}</p>
      <ul className="mt-3 space-y-1 text-xs text-slate-600">
        {result.lines.map((l) => (
          <li key={l.label} className="flex justify-between gap-3"><span>{l.label}</span><span className="font-mono">{gbp(l.amount)}</span></li>
        ))}
      </ul>
      {result.total != null && (
        <div className="mt-3 flex items-end justify-between border-t border-slate-100 pt-3">
          <span className="text-xs text-slate-500">Total</span>
          <span className="font-mono text-2xl font-bold text-teal-700" data-testid="chat-quote-total">{gbp(result.total)}</span>
        </div>
      )}
      {result.reasons?.map((r) => (
        <p key={r} className="mt-2 flex gap-2 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5 shrink-0" />{r}</p>
      ))}
      {ok && (
        <button onClick={() => navigate(`${base}/quote?q=${quoteId}&t=${encodeURIComponent(quoteToken || "")}`)} data-testid="chat-quote-book-btn"
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-full bg-teal-600 py-2 text-sm font-medium text-white transition-colors hover:bg-teal-700">
          Book this quote <ArrowRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
