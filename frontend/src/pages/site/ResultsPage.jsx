import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";
import { api, fmtDate } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

const API = process.env.REACT_APP_BACKEND_URL;

const Column = ({ title, photos, src }) => (
  <section data-testid={`results-${title.toLowerCase()}`}>
    <h2 className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#8F7E22]">{title}</h2>
    <div className="mt-3 grid grid-cols-2 gap-3">
      {photos.map((p) => <a key={p.id} href={src(p.id)} target="_blank" rel="noreferrer"><img src={src(p.id)} alt={`${title} photo`} loading="lazy" className="aspect-square w-full rounded-2xl object-cover" /></a>)}
      {!photos.length && <p className="col-span-2 text-sm text-slate-400">No {title.toLowerCase()} photos.</p>}
    </div>
  </section>
);

export default function ResultsPage() {
  const { bookingId } = useParams();
  const [params] = useSearchParams();
  const t = params.get("t") || "";
  const base = `/public/${DEFAULT_SLUG}/photos/results/${bookingId}`;
  const [d, setD] = useState(null);
  useEffect(() => { api.get(base, { params: { t } }).then((r) => setD(r.data)).catch(() => setD("invalid")); }, [base, t]);
  if (!d) return <div className="p-24 text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-[#023F00]" /></div>;
  if (d === "invalid") return <main className="mx-auto max-w-xl px-4 py-24 text-center" data-testid="results-invalid"><h1 className="text-3xl font-bold text-slate-900">This link is not valid</h1><p className="mt-3 text-slate-600">Please use the link from your email.</p></main>;
  const src = (pid) => `${API}/api${base}/${pid}?t=${encodeURIComponent(t)}`;
  return (
    <main className="mx-auto max-w-6xl px-4 py-14 sm:py-20" data-testid="results-page">
      <Sparkles className="h-9 w-9 text-[#8F7E22]" />
      <h1 className="mt-5 text-4xl font-extrabold tracking-tight text-[#023F00] sm:text-5xl">Your before & after photos</h1>
      <p className="mt-4 text-slate-600">Hi {d.first_name}, here are the photos from your {d.service_name} on <b>{fmtDate(d.date)}</b>. Thank you for choosing Solid Clean Ltd.</p>
      <div className="mt-10 grid gap-10 md:grid-cols-2">
        <Column title="Before" photos={d.photos.filter((p) => p.kind === "before")} src={src} />
        <Column title="After" photos={d.photos.filter((p) => p.kind === "after")} src={src} />
      </div>
    </main>
  );
}
