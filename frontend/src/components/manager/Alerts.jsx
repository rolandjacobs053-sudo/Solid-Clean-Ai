import { AlertTriangle, Info } from "lucide-react";
import { useLoad } from "@/components/admin/ui";

const TONE = { high: "border-red-200 bg-red-50 text-red-900", medium: "border-amber-200 bg-amber-50 text-amber-900", low: "border-slate-200 bg-white text-slate-700" };

export const Alerts = () => {
  const [list] = useLoad("/admin/strategy/insights");
  if (!list?.length) return null;
  return (
    <div className="mb-5" data-testid="manager-alerts">
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Spotted in your data</p>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {list.map((a, i) => (
          <div key={i} className={`min-w-[260px] max-w-[300px] shrink-0 rounded-xl border p-3 ${TONE[a.severity]}`} data-testid={`manager-alert-${i}`}>
            <p className="flex items-center gap-1.5 text-sm font-semibold">{a.severity === "low" ? <Info className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}{a.title}</p>
            <p className="mt-1 text-xs leading-relaxed">{a.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
