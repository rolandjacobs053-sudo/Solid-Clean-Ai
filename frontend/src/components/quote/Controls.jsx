import { Minus, Plus } from "lucide-react";

export function Counter({ label, value, onChange, min = 0, max = 10, testid }) {
  const btn = "grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-white transition-colors hover:border-teal-500 hover:text-teal-700 disabled:opacity-40";
  return (
    <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-4">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="flex items-center gap-3">
        <button type="button" className={btn} disabled={value <= min} onClick={() => onChange(value - 1)} data-testid={`${testid}-minus`}><Minus className="h-4 w-4" /></button>
        <span className="w-6 text-center font-mono text-lg font-semibold" data-testid={testid}>{value}</span>
        <button type="button" className={btn} disabled={value >= max} onClick={() => onChange(value + 1)} data-testid={`${testid}-plus`}><Plus className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

export function ChoiceCard({ active, onClick, title, sub, testid }) {
  return (
    <button type="button" onClick={onClick} data-testid={testid}
      className={`rounded-2xl border p-4 text-left transition-colors ${active ? "border-teal-600 bg-teal-50 ring-1 ring-teal-600" : "border-slate-200 bg-white hover:border-teal-300"}`}>
      <p className="font-display text-sm font-semibold text-slate-900">{title}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </button>
  );
}
