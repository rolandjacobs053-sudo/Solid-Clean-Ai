import { useOutletContext } from "react-router-dom";
import { fmtDate } from "@/lib/api";

export default function PublicPolicies() {
  const cfg = useOutletContext();
  if (!cfg) return null;
  return (
    <main className="mx-auto max-w-3xl px-4 py-12" data-testid="public-policies-page">
      <p className="eyebrow">Company policies</p>
      <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-slate-900">{cfg.business.name} policies</h1>
      {cfg.policies.length === 0 && <p className="mt-6 text-slate-500">Policies are being finalised. Please contact us{cfg.business.phone ? ` on ${cfg.business.phone}` : ""} with any questions.</p>}
      {cfg.policies.map((p) => (
        <section key={p.key} id={p.key} className="mt-10 scroll-mt-24" data-testid={`public-policy-${p.key}`}>
          <h2 className="text-xl font-bold text-slate-900">{p.title}</h2>
          <p className="mt-1 font-mono text-xs text-slate-400">Version {p.published_version} · effective {fmtDate(p.effective_date)}</p>
          <p className="mt-3 whitespace-pre-wrap leading-relaxed text-slate-700">{p.published_content}</p>
        </section>
      ))}
    </main>
  );
}
