import { useState } from "react";
import { Check, ListChecks, Loader2, RefreshCw, ThumbsUp, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/api";

const TONE = { high: "bg-red-100 text-red-700", medium: "bg-amber-100 text-amber-800", low: "bg-slate-100 text-slate-600" };
const Row = ({ k, v }) => <div><dt className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{k}</dt><dd className="text-sm text-slate-700">{v || "—"}</dd></div>;

const Card = ({ p, onChange }) => {
  const [busy, setBusy] = useState(false);
  const patch = async (body) => { try { onChange((await api.patch(`/admin/manager/priorities/${p.id}`, body)).data); } catch (e) { toast.error(errMsg(e)); } };
  const plan = async () => { setBusy(true); try { onChange((await api.post(`/admin/manager/priorities/${p.id}/plan`)).data); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  const toggle = (i) => patch({ checklist: p.checklist.map((c, j) => (j === i ? { ...c, done: !c.done } : c)) });
  return (
    <article className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5" data-testid={`priority-card-${p.id}`}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-display text-base font-semibold text-slate-900">{p.title}</h3>
        <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase ${TONE[p.priority]}`}>{p.priority}</span>
      </div>
      <div className="mt-1"><StatusBadge status={p.status} testid={`priority-status-${p.id}`} /></div>
      <dl className="mt-4 grid gap-3">
        <Row k="What to do" v={p.what} /><Row k="Why it matters" v={p.why} /><Row k="Expected benefit" v={p.benefit} /><Row k="Estimated cost" v={p.cost} /><Row k="How to measure" v={p.measure} />
      </dl>
      {p.checklist?.length > 0 && (
        <ul className="mt-4 space-y-2 rounded-xl bg-slate-50 p-3" data-testid={`priority-checklist-${p.id}`}>
          {p.checklist.map((c, i) => <li key={i} className="flex items-start gap-2 text-sm"><Checkbox checked={c.done} onCheckedChange={() => toggle(i)} className="mt-0.5" data-testid={`priority-check-${p.id}-${i}`} /><span className={c.done ? "text-slate-400 line-through" : ""}>{c.text}</span></li>)}
        </ul>
      )}
      <div className="mt-auto flex flex-wrap gap-2 pt-4">
        {p.status === "suggested" && <Button size="sm" onClick={() => patch({ status: "approved" })} className="bg-[#023F00] hover:bg-[#012b00]" data-testid={`priority-approve-${p.id}`}><ThumbsUp className="mr-1 h-3.5 w-3.5" />Approve</Button>}
        {p.status !== "completed" && <Button size="sm" variant="outline" onClick={() => patch({ status: "completed" })} data-testid={`priority-complete-${p.id}`}><Check className="mr-1 h-3.5 w-3.5" />Mark done</Button>}
        {p.status !== "dismissed" && p.status !== "completed" && <Button size="sm" variant="ghost" onClick={() => patch({ status: "dismissed" })} data-testid={`priority-dismiss-${p.id}`}><X className="mr-1 h-3.5 w-3.5" />Dismiss</Button>}
        {p.status !== "dismissed" && <Button size="sm" variant="outline" onClick={plan} disabled={busy} data-testid={`priority-plan-${p.id}`}>{busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <ListChecks className="mr-1 h-3.5 w-3.5" />}{p.checklist?.length ? "Rebuild checklist" : "Make a checklist"}</Button>}
      </div>
    </article>
  );
};

export const Priorities = () => {
  const [list, reload] = useLoad("/admin/manager/priorities");
  const [busy, setBusy] = useState(false);
  const gen = async () => { setBusy(true); try { await api.post("/admin/manager/priorities/generate"); reload(); toast.success("Priorities updated from your latest data"); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  const active = (list || []).filter((p) => ["suggested", "approved"].includes(p.status)).slice(0, 3);
  const past = (list || []).filter((p) => ["completed", "dismissed"].includes(p.status));
  return (
    <div data-testid="manager-priorities">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-slate-600">Up to three actions based on your actual dashboard data. Approving an action only records your decision - nothing is sent or changed.</p>
        <Button onClick={gen} disabled={busy} className="rounded-full bg-[#8F7E22] hover:bg-[#7a6b1d]" data-testid="priorities-generate-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}{busy ? "Analysing your business…" : "Refresh my priorities"}</Button>
      </div>
      {list && !active.length && <Empty>No active priorities yet - tap "Refresh my priorities".</Empty>}
      <div className="grid gap-4 lg:grid-cols-3">{active.map((p) => <Card key={p.id} p={p} onChange={reload} />)}</div>
      {past.length > 0 && (
        <details className="mt-8" data-testid="priorities-history">
          <summary className="cursor-pointer text-sm font-medium text-slate-600">Completed and dismissed ({past.length})</summary>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">{past.map((p) => <Card key={p.id} p={p} onChange={reload} />)}</div>
        </details>
      )}
    </div>
  );
};
