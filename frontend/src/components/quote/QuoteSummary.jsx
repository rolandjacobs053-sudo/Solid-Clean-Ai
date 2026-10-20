import { AlertTriangle } from "lucide-react";
import { gbp } from "@/lib/api";

export function QuoteSummary({ preview, form, date, slot, config }) {
  const svc = config?.pricing.services.find((s) => s.key === form.service);
  return (
    <aside className="sticky top-24 rounded-3xl border border-slate-200 bg-white p-7 shadow-xl shadow-slate-900/5" data-testid="quote-summary">
      <p className="eyebrow">Your quote</p>
      <h3 className="mt-2 font-display text-xl font-semibold text-slate-900">{svc?.name || "Choose a service"}</h3>
      <ul className="mt-5 space-y-2 text-sm text-slate-600">
        {preview?.lines?.map((l) => (
          <li key={l.label} className="flex justify-between gap-4"><span>{l.label}</span><span className="font-mono">{gbp(l.amount)}</span></li>
        ))}
      </ul>
      <div className="mt-6 flex items-end justify-between border-t border-dashed border-slate-200 pt-5">
        <span className="text-sm text-slate-500">Total</span>
        <span className="font-mono text-4xl font-bold tracking-tight text-teal-700" data-testid="quote-calculated-price-display">
          {preview?.total != null ? gbp(preview.total) : "—"}
        </span>
      </div>
      {preview?.reasons?.map((r) => (
        <p key={r} className="mt-3 flex gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-800" data-testid="quote-review-reason"><AlertTriangle className="h-4 w-4 shrink-0" />{r}</p>
      ))}
      {date && (
        <p className="mt-5 rounded-xl bg-teal-50 p-3 font-mono text-xs text-teal-800" data-testid="quote-selected-slot">
          {date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} {slot ? `· ${slot}` : "· choose a time"}
        </p>
      )}
      <p className="mt-5 text-xs text-slate-400">Calculated from Solid Clean's approved price list. {config?.business?.payment_mode === "deposit_50" ? `A 50% deposit${preview?.deposit != null ? ` (${gbp(preview.deposit)})` : ""} confirms your booking; the balance is due after the clean.` : "Full payment secures your slot."}</p>
    </aside>
  );
}
