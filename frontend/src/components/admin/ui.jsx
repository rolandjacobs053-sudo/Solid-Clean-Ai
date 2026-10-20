import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg, label } from "@/lib/api";

export function useLoad(path, params) {
  const [data, setData] = useState(null);
  const key = JSON.stringify(params || {});
  const reload = useCallback(() => {
    api.get(path, { params: JSON.parse(key) }).then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [path, key]);
  useEffect(() => { reload(); }, [reload]);
  return [data, reload];
}

export const PageHeader = ({ eyebrow, title, desc, children }) => (
  <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
    <div>
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">{title}</h1>
      {desc && <p className="mt-2 max-w-2xl text-sm text-slate-500">{desc}</p>}
    </div>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);

export const Kpi = ({ label: l, value, hint, testid, accent }) => (
  <div className={`rounded-2xl border p-5 ${accent ? "border-teal-700 bg-teal-700 text-white" : "border-slate-200 bg-white"}`} data-testid={testid}>
    <p className={`font-mono text-[10px] uppercase tracking-[0.18em] ${accent ? "text-teal-100" : "text-slate-500"}`}>{l}</p>
    <p className="mt-3 font-mono text-2xl font-bold tracking-tight sm:text-3xl" data-testid={`${testid}-value`}>{value}</p>
    {hint && <p className={`mt-1 text-xs ${accent ? "text-teal-100" : "text-slate-400"}`}>{hint}</p>}
  </div>
);

const TONES = {
  new: "bg-sky-100 text-sky-800", quoted: "bg-amber-100 text-amber-800", sent: "bg-amber-100 text-amber-800",
  booked: "bg-teal-100 text-teal-800", confirmed: "bg-teal-100 text-teal-800", accepted: "bg-teal-100 text-teal-800",
  completed: "bg-emerald-600 text-white", paid: "bg-emerald-100 text-emerald-800", lost: "bg-slate-200 text-slate-600",
  cancelled: "bg-slate-200 text-slate-600", abandoned: "bg-slate-100 text-slate-500", pending_payment: "bg-orange-100 text-orange-800",
  needs_human: "bg-red-100 text-red-700", needs_attention: "bg-red-100 text-red-700", needs_review: "bg-orange-100 text-orange-800",
  opted_out: "bg-red-100 text-red-700", blocked_opt_out: "bg-red-100 text-red-700", simulated: "bg-violet-100 text-violet-800", sent: "bg-emerald-100 text-emerald-800", failed: "bg-red-100 text-red-700", paused: "bg-orange-100 text-orange-800", no_address: "bg-slate-200 text-slate-600",
  scheduled: "bg-sky-100 text-sky-800", interested: "bg-teal-100 text-teal-800", meeting: "bg-emerald-100 text-emerald-800",
  won: "bg-emerald-600 text-white", contacted: "bg-amber-100 text-amber-800", draft_ready: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800", responded: "bg-emerald-100 text-emerald-800", resolved: "bg-slate-200 text-slate-600",
};

export const StatusBadge = ({ status, testid }) => (
  <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${TONES[status] || "bg-slate-100 text-slate-600"}`} data-testid={testid}>
    {label(status)}
  </span>
);

export const DemoTag = ({ show }) => show ? <span className="ml-2 rounded bg-slate-900 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-white">demo</span> : null;

export const Panel = ({ title, children, action, className = "" }) => (
  <section className={`rounded-2xl border border-slate-200 bg-white ${className}`}>
    {title && <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><h3 className="font-display text-sm font-semibold text-slate-900">{title}</h3>{action}</div>}
    <div className="p-5">{children}</div>
  </section>
);

export const Notice = ({ children, testid }) => (
  <div className="mb-6 rounded-2xl border border-violet-200 bg-violet-50 px-5 py-3 text-sm text-violet-900" data-testid={testid}>{children}</div>
);

export const Empty = ({ children }) => <p className="py-8 text-center text-sm text-slate-400">{children}</p>;
