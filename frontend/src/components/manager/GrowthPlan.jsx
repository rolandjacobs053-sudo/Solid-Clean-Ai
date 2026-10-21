import { useState } from "react";
import { Loader2, Map, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Empty, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDateTime } from "@/lib/api";

const num = (v) => (typeof v === "number" ? v.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : v ?? "—");

const Goals = () => {
  const [d, reload] = useLoad("/admin/strategy/goals");
  const [v, setV] = useState({ title: "", metric: "monthly_revenue", target: "" });
  const add = async () => { try { await api.post("/admin/strategy/goals", { ...v, target: Number(v.target) }); setV({ ...v, title: "", target: "" }); reload(); toast.success("Goal added"); } catch (e) { toast.error(errMsg(e)); } };
  const del = async (id) => { await api.delete(`/admin/strategy/goals/${id}`); reload(); };
  return (
    <Panel title="Goals & progress (actual figures)">
      <div className="space-y-4" data-testid="goals-list">
        {d?.goals.map((g) => (
          <div key={g.id} data-testid={`goal-${g.id}`}>
            <div className="flex items-baseline justify-between gap-2 text-sm"><span className="font-medium text-slate-900">{g.title}</span><span className="font-mono text-xs text-slate-500" data-testid={`goal-progress-${g.id}`}>{num(g.current)} / {num(g.target)} ({g.progress_pct < 1 ? g.progress_pct.toFixed(3) : g.progress_pct.toFixed(1)}%)</span></div>
            <Progress value={g.progress_pct} className="mt-1.5 h-2" />
            <div className="mt-1 flex justify-between text-[11px] text-slate-400"><span>{g.metric_label}</span><button onClick={() => del(g.id)} className="hover:text-red-600" aria-label="Remove goal" data-testid={`goal-delete-${g.id}`}><Trash2 className="h-3.5 w-3.5" /></button></div>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-2 border-t pt-4 sm:grid-cols-[1fr_220px_130px_auto]">
        <Input placeholder="Goal, e.g. 20 regular clients" value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} data-testid="goal-title-input" />
        <Select value={v.metric} onValueChange={(m) => setV({ ...v, metric: m })}><SelectTrigger data-testid="goal-metric-select"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(d?.metrics || {}).map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent></Select>
        <Input type="number" placeholder="Target" value={v.target} onChange={(e) => setV({ ...v, target: e.target.value })} data-testid="goal-target-input" />
        <Button onClick={add} disabled={!v.title || !(Number(v.target) > 0)} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="goal-add-btn"><Plus className="h-4 w-4" /></Button>
      </div>
    </Panel>
  );
};

const Stage = ({ s, current }) => (
  <details open={s.n === current} className={`rounded-2xl border p-4 ${s.n === current ? "border-[#8F7E22] bg-[#8F7E22]/5" : s.n < current ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200 bg-white"}`} data-testid={`roadmap-stage-${s.n}`}>
    <summary className="cursor-pointer list-none">
      <div className="flex flex-wrap items-center gap-3"><span className={`flex h-8 w-8 items-center justify-center rounded-full font-mono text-sm font-bold ${s.n === current ? "bg-[#8F7E22] text-white" : "bg-slate-100 text-slate-600"}`}>{s.n}</span>
        <span className="flex-1 font-display font-semibold text-slate-900">{s.name}{s.n === current && <span className="ml-2 rounded-full bg-[#8F7E22] px-2 py-0.5 font-mono text-[9px] uppercase text-white">You are here</span>}</span>
        <span className="font-mono text-xs text-slate-500">{s.timeframe_estimate}</span></div>
      <p className="mt-2 text-sm text-slate-600">{s.goal}</p>
    </summary>
    <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
      {[["Annual revenue", s.annual_revenue], ["Monthly profit", s.monthly_profit], ["Staff", s.staff], ["Customers", s.customers], ["Contracts", s.contracts], ["Investment", s.investment]].map(([k, v]) => <div key={k}><p className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{k}</p><p className="text-slate-800">{v}</p></div>)}
    </div>
    {[["Key actions", s.key_actions], ["Move on when", s.exit_criteria], ["Systems", s.systems], ["Risks", s.risks], ["Evidence used", s.evidence], ["Assumptions", s.assumptions]].map(([k, arr]) => arr?.length ? <div key={k} className="mt-3"><p className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{k}</p><ul className="ml-4 list-disc text-sm text-slate-700">{arr.map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null)}
  </details>
);

export const GrowthPlan = () => {
  const [rm, reload] = useLoad("/admin/strategy/roadmap");
  const [busy, setBusy] = useState(false);
  const gen = async () => { setBusy(true); try { await api.post("/admin/strategy/roadmap/generate"); reload(); toast.success("Roadmap updated from your latest data"); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  return (
    <div className="grid gap-6" data-testid="manager-growth-plan">
      <Goals />
      <Panel title="Roadmap to £400 million" action={<Button size="sm" onClick={gen} disabled={busy} className="rounded-full bg-[#8F7E22] hover:bg-[#7a6b1d]" data-testid="roadmap-generate-btn">{busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Map className="mr-1 h-3.5 w-3.5" />}{busy ? "Analysing… (about a minute)" : rm ? "Rebuild from latest data" : "Build my roadmap"}</Button>}>
        {!rm ? <Empty>No roadmap yet. It's built from your real figures plus the industry knowledge base, with every estimate labelled.</Empty> : (
          <div className="space-y-4" data-testid="roadmap">
            <p className="text-xs text-slate-400">Built {fmtDateTime(rm.created_at)} · {rm.knowledge_used} knowledge-base lessons used · all future figures are estimates</p>
            <div className="rounded-xl bg-slate-50 p-4 text-sm"><p className="font-semibold text-slate-900">Where you are now (stage {rm.current_stage})</p><p className="mt-1 text-slate-700" data-testid="roadmap-position">{rm.current_position}</p></div>
            <div className="rounded-xl border border-slate-200 p-4 text-sm"><p className="font-semibold text-slate-900">£400m revenue vs £400m valuation</p><p className="mt-1 whitespace-pre-wrap text-slate-700" data-testid="roadmap-valuation">{rm.revenue_vs_valuation}</p></div>
            {rm.next_90_days?.length > 0 && <div className="rounded-xl border border-[#023F00]/20 bg-[#023F00]/5 p-4 text-sm"><p className="font-semibold text-slate-900">Next 90 days</p><ol className="ml-4 mt-1 list-decimal text-slate-700">{rm.next_90_days.map((x, i) => <li key={i}>{x}</li>)}</ol></div>}
            {rm.stages.map((s) => <Stage key={s.n} s={s} current={rm.current_stage} />)}
          </div>
        )}
      </Panel>
    </div>
  );
};
