import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/admin/ui";
import { QUOTE_INTRO, QUOTE_NOTES, QUOTE_TABLES } from "@/lib/quotation";

export default function Quotation() {
  return (
    <div className="max-w-5xl" data-testid="platform-quotation-page">
      <PageHeader eyebrow="Quotation" title="CleanOps SaaS - MVP & full platform" desc={QUOTE_INTRO}>
        <Button variant="outline" onClick={() => window.print()} data-testid="quotation-print-btn"><Printer className="mr-2 h-4 w-4" />Print / PDF</Button>
      </PageHeader>
      <div className="space-y-10">
        {QUOTE_TABLES.map((s) => (
          <section key={s.t} data-testid="quotation-section">
            <h2 className="text-xl font-bold tracking-tight text-slate-900">{s.t}</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead><tr>{s.rows[0].map((h) => <th key={h} className="border-b px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-slate-500">{h}</th>)}</tr></thead>
                <tbody>{s.rows.slice(1).map((r) => <tr key={r[0]} className={`border-b last:border-0 ${r[0].includes("total") ? "bg-teal-50 font-semibold" : ""}`}>{r.map((c, i) => <td key={i} className={`px-4 py-2 ${i === 2 ? "whitespace-nowrap font-mono" : ""}`}>{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </section>
        ))}
        <ul className="space-y-2 text-sm text-slate-600">{QUOTE_NOTES.map((n) => <li key={n}>— {n}</li>)}</ul>
      </div>
    </div>
  );
}
