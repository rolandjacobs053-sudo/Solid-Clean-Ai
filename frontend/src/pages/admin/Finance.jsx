import { useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Empty, Kpi, PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, gbp, label } from "@/lib/api";

const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Europe/London" });
const thisMonth = () => today().slice(0, 7);

const ExpenseForm = ({ categories, onAdded }) => {
  const [v, setV] = useState({ date: today(), category: "supplies", amount: "", description: "" });
  const add = async () => {
    try { await api.post("/admin/finance/expenses", { ...v, amount: Number(v.amount) }); setV({ ...v, amount: "", description: "" }); onAdded(); toast.success("Expense recorded"); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="grid gap-2 sm:grid-cols-[140px_170px_110px_1fr_auto]" data-testid="expense-form">
      <Input type="date" value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} data-testid="expense-date-input" />
      <Select value={v.category} onValueChange={(category) => setV({ ...v, category })}>
        <SelectTrigger data-testid="expense-category-select"><SelectValue /></SelectTrigger>
        <SelectContent>{categories.map((c) => <SelectItem key={c} value={c} className="capitalize">{label(c)}</SelectItem>)}</SelectContent>
      </Select>
      <Input type="number" step="0.01" min="0" placeholder="£ amount" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} data-testid="expense-amount-input" />
      <Input placeholder="Description (optional)" value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} data-testid="expense-description-input" />
      <Button onClick={add} disabled={!(Number(v.amount) > 0)} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="expense-add-btn"><Plus className="mr-1 h-4 w-4" />Add</Button>
    </div>
  );
};

const JobRow = ({ j, onSaved }) => {
  const [c, setC] = useState({ cleaner_pay: j.job_costs?.cleaner_pay ?? "", supplies: j.job_costs?.supplies ?? "", travel: j.job_costs?.travel ?? "" });
  const save = async () => { try { await api.put(`/admin/finance/jobs/${j.id}/costs`, { cleaner_pay: Number(c.cleaner_pay) || 0, supplies: Number(c.supplies) || 0, travel: Number(c.travel) || 0 }); onSaved(); toast.success("Job costs saved"); } catch (e) { toast.error(errMsg(e)); } };
  const cost = ["cleaner_pay", "supplies", "travel"].reduce((s, k) => s + (Number(c[k]) || 0), 0);
  return (
    <tr className="border-t border-slate-100" data-testid={`job-cost-row-${j.id}`}>
      <td className="py-2 pr-3 font-mono text-xs">{fmtDate(j.date)}</td>
      <td className="py-2 pr-3 text-sm">{j.service}{j.demo && <span className="ml-1 rounded bg-slate-900 px-1 font-mono text-[9px] text-white">DEMO</span>}<p className="text-xs text-slate-400">{j.customer} · {j.postcode}</p></td>
      <td className="py-2 pr-3 font-mono text-sm">{gbp(j.total)}</td>
      {["cleaner_pay", "supplies", "travel"].map((k) => <td key={k} className="py-2 pr-2"><Input type="number" min="0" step="0.01" value={c[k]} onChange={(e) => setC({ ...c, [k]: e.target.value })} className="w-24 font-mono" placeholder="0" data-testid={`job-cost-${j.id}-${k}`} /></td>)}
      <td className="py-2 pr-3 font-mono text-sm" data-testid={`job-profit-${j.id}`}>{j.job_costs || cost ? gbp(j.total - cost) : <span className="text-xs text-amber-600">not costed</span>}</td>
      <td className="py-2"><Button size="sm" variant="outline" onClick={save} data-testid={`job-cost-save-${j.id}`}><Save className="h-3.5 w-3.5" /></Button></td>
    </tr>
  );
};

export default function Finance() {
  const [month, setMonth] = useState(thisMonth());
  const [sum, reloadSum] = useLoad("/admin/finance/summary", { month });
  const [exps, reloadExp] = useLoad("/admin/finance/expenses", { month });
  const [jobs, reloadJobs] = useLoad("/admin/finance/jobs", { month });
  const reload = () => { reloadSum(); reloadExp(); reloadJobs(); };
  const m = sum?.metrics;
  const del = async (id) => { try { await api.delete(`/admin/finance/expenses/${id}`); toast.success("Expense deleted"); } catch (e) { toast.error(errMsg(e)); } reload(); };
  return (
    <div data-testid="finance-page">
      <PageHeader eyebrow="Private · owner only" title="Expenses & profit" desc="Record expenses and the cost of each job so revenue and profit are calculated from real figures. Demo records are excluded from totals.">
        <Input type="month" value={month} onChange={(e) => setMonth(e.target.value || thisMonth())} className="w-44" data-testid="finance-month-input" />
      </PageHeader>
      {m && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Kpi label="Revenue (paid jobs)" value={gbp(m.revenue)} hint={`${m.jobs_booked_or_done} jobs`} testid="finance-kpi-revenue" />
          <Kpi label="Job costs" value={gbp(m.job_costs_recorded)} hint={m.jobs_missing_costs ? `${m.jobs_missing_costs} jobs not costed` : "all jobs costed"} testid="finance-kpi-jobcosts" />
          <Kpi label="Expenses" value={gbp(m.expenses_recorded)} testid="finance-kpi-expenses" />
          <Kpi label="Marketing spend" value={gbp(m.marketing_spend)} testid="finance-kpi-marketing" />
          <Kpi label="Profit" value={gbp(m.profit)} hint={m.profit_status} accent testid="finance-kpi-profit" />
        </div>
      )}
      <div className="grid gap-6">
        <Panel title="Record an expense"><ExpenseForm categories={sum?.categories || []} onAdded={reload} />
          <ul className="mt-4 divide-y" data-testid="expense-list">
            {exps?.map((e) => <li key={e.id} className="flex items-center gap-3 py-2 text-sm" data-testid={`expense-item-${e.id}`}><span className="w-24 font-mono text-xs">{fmtDate(e.date)}</span><span className="w-40 capitalize text-slate-500">{label(e.category)}</span><span className="flex-1">{e.description}</span><span className="font-mono">{gbp(e.amount)}</span><button onClick={() => del(e.id)} className="text-slate-400 hover:text-red-600" aria-label="Delete expense" data-testid={`expense-delete-${e.id}`}><Trash2 className="h-4 w-4" /></button></li>)}
          </ul>
          {exps?.length === 0 && <Empty>No expenses recorded this month.</Empty>}
        </Panel>
        <Panel title="Cost per job (cleaner pay, supplies, travel)">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px]" data-testid="job-costs-table">
              <thead><tr className="text-left font-mono text-[10px] uppercase tracking-wider text-slate-500"><th className="py-2">Date</th><th>Job</th><th>Price</th><th>Cleaner pay</th><th>Supplies</th><th>Travel</th><th>Job profit</th><th /></tr></thead>
              <tbody>{jobs?.map((j) => <JobRow key={j.id} j={j} onSaved={reload} />)}</tbody>
            </table>
          </div>
          {jobs?.length === 0 && <Empty>No paid jobs dated in this month.</Empty>}
        </Panel>
      </div>
    </div>
  );
}
