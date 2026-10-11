import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/admin/ui";
import { SECTIONS, STATUS } from "@/lib/proposal";

const Tbl = ({ rows }) => (
  <div className="mt-4 overflow-x-auto">
    <table className="w-full text-sm">
      <thead><tr>{rows[0].map((h) => <th key={h} className="border-b border-slate-300 py-2 pr-4 text-left font-mono text-[10px] uppercase tracking-wider text-slate-500">{h}</th>)}</tr></thead>
      <tbody>{rows.slice(1).map((r) => <tr key={r[0]} className="border-b border-slate-100">{r.map((c, i) => <td key={i} className={`py-2 pr-4 ${i === r.length - 1 ? "font-mono" : ""}`}>{c}</td>)}</tr>)}</tbody>
    </table>
  </div>
);

export default function Proposal() {
  return (
    <div className="max-w-4xl" data-testid="admin-proposal-page">
      <PageHeader eyebrow="Proposal" title="Solid Clean Ltd - integrated AI growth system" desc="Answers to the 12 questions in your brief, plus the status of what has already been built.">
        <Button variant="outline" onClick={() => window.print()} data-testid="proposal-print-btn"><Printer className="mr-2 h-4 w-4" />Print / PDF</Button>
      </PageHeader>
      <section className="rounded-2xl bg-slate-950 p-6 text-white" data-testid="proposal-status">
        <p className="eyebrow !text-teal-400">Built in this first version</p>
        <ul className="mt-4 divide-y divide-slate-800">
          {STATUS.map(([t, s]) => <li key={t} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><span>{t}</span><span className="font-mono text-xs text-teal-300">{s}</span></li>)}
        </ul>
      </section>
      <div className="mt-10 space-y-12">
        {SECTIONS.map((s) => (
          <article key={s.n} data-testid={`proposal-section-${s.n}`}>
            <div className="flex items-baseline gap-4"><span className="font-mono text-sm text-teal-600">{s.n}</span><h2 className="text-2xl font-bold tracking-tight text-slate-900">{s.t}</h2></div>
            {s.p?.map((x) => <p key={x} className="mt-4 leading-relaxed text-slate-600">{x}</p>)}
            {s.l && <ul className="mt-4 space-y-2">{s.l.map((x) => <li key={x} className="flex gap-3 text-slate-600"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600" />{x}</li>)}</ul>}
            {s.table && <Tbl rows={s.table} />}
            {s.note && <p className="mt-3 text-xs text-slate-400">{s.note}</p>}
          </article>
        ))}
      </div>
    </div>
  );
}
