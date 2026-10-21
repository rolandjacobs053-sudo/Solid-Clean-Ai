import { useState } from "react";
import { ExternalLink, Globe, Loader2, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Empty, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, label } from "@/lib/api";

const LEVEL = { verified: "bg-emerald-100 text-emerald-800", reported: "bg-sky-100 text-sky-800", claim: "bg-amber-100 text-amber-800", opinion: "bg-slate-100 text-slate-600" };

const AddSource = ({ types, onAdded }) => {
  const [v, setV] = useState({ url: "", text: "", title: "", source_type: "web" });
  const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { const { data } = await api.post("/admin/knowledge/ingest", v); toast.success(`${data.added} lessons added from "${data.source_title}"${data.duplicates ? ` (${data.duplicates} duplicates skipped)` : ""}`); setV({ ...v, url: "", text: "", title: "" }); onAdded(); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  return (
    <Panel title="Add a source">
      <div className="grid gap-2" data-testid="knowledge-add-form">
        <div className="grid gap-2 sm:grid-cols-[1fr_160px]">
          <Input placeholder="https:// web page or YouTube link" value={v.url} onChange={(e) => setV({ ...v, url: e.target.value })} data-testid="knowledge-url-input" />
          <Select value={v.source_type} onValueChange={(x) => setV({ ...v, source_type: x })}><SelectTrigger data-testid="knowledge-type-select"><SelectValue /></SelectTrigger><SelectContent>{types.map((t) => <SelectItem key={t} value={t} className="capitalize">{label(t)}</SelectItem>)}</SelectContent></Select>
        </div>
        <Input placeholder="Title (for pasted text, e.g. book or podcast name)" value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} data-testid="knowledge-title-input" />
        <Textarea rows={3} placeholder="…or paste text you're allowed to use: your book notes, a podcast/YouTube transcript, a TikTok/Instagram caption" value={v.text} onChange={(e) => setV({ ...v, text: e.target.value })} data-testid="knowledge-text-input" />
        <Button onClick={go} disabled={busy || (!v.url && v.text.length < 200)} className="justify-self-start bg-[#023F00] hover:bg-[#012b00]" data-testid="knowledge-ingest-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}{busy ? "Reading and extracting lessons…" : "Read & extract lessons"}</Button>
      </div>
    </Panel>
  );
};

const Lesson = ({ k, onChange }) => {
  const patch = async (status) => { await api.patch(`/admin/knowledge/${k.id}`, { status }); onChange(); };
  const del = async () => { await api.delete(`/admin/knowledge/${k.id}`); onChange(); };
  return (
    <article className={`rounded-xl border bg-white p-4 ${k.status === "outdated" ? "opacity-70" : ""}`} data-testid={`knowledge-item-${k.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="flex-1 font-semibold text-slate-900">{k.title}</h4>
        <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] uppercase ${LEVEL[k.evidence_level]}`}>{k.evidence_level}</span>
        {k.status === "outdated" && <span className="rounded-full bg-red-100 px-2 py-0.5 font-mono text-[10px] uppercase text-red-700">possibly outdated</span>}
      </div>
      <p className="mt-1 text-xs text-slate-500">{k.who} · {label(k.topic)} · {k.region}{k.published ? ` · published ${k.published}` : ""}</p>
      <p className="mt-2 text-sm text-slate-700">{k.lesson}</p>
      {k.evidence && <p className="mt-2 text-xs text-slate-500"><b>Evidence:</b> {k.evidence}</p>}
      {k.implementation && <p className="mt-1 text-xs text-slate-600"><b>For Solid Clean:</b> {k.implementation}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
        {k.source_url ? <a href={k.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[#023F00] hover:underline" data-testid={`knowledge-source-${k.id}`}><ExternalLink className="h-3 w-3" />{k.source_title}</a> : <span className="text-slate-500">{k.source_title}</span>}
        <span className="text-slate-400">read {fmtDate(k.retrieved_at)}</span>
        <button onClick={() => patch(k.status === "outdated" ? "active" : "outdated")} className="ml-auto text-slate-500 hover:text-slate-800" data-testid={`knowledge-toggle-outdated-${k.id}`}>{k.status === "outdated" ? "Mark current" : "Flag outdated"}</button>
        <button onClick={del} className="text-slate-400 hover:text-red-600" aria-label="Delete lesson" data-testid={`knowledge-delete-${k.id}`}><Trash2 className="h-3.5 w-3.5" /></button>
      </div>
    </article>
  );
};

const Research = ({ onDone }) => {
  const [st, reload] = useLoad("/admin/knowledge/research/status");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (t) => {
    setBusy(true);
    try {
      await api.post("/admin/knowledge/research", { topic: t });
      for (let i = 0; i < 40; i += 1) {
        await new Promise((r) => setTimeout(r, 3000));
        const { data } = await api.get("/admin/strategy/jobs/research");
        if (data.status === "done") { toast.success(`Research complete: ${data.result_id}`); onDone(); break; }
        if (data.status === "failed") { toast.error(data.error); break; }
        if (i === 39) toast.message("Still researching - check back in a few minutes.");
      }
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
    reload();
  };
  if (!st) return null;
  return (
    <Panel title="Live web research (Perplexity)">
      <div data-testid="knowledge-research-panel">
        {!st.connected ? (
          <p className="text-sm text-amber-800" data-testid="research-not-connected">Not connected yet. Create an API key at perplexity.ai/settings/api (pay-as-you-go, typically a few pence per search) and send it to me - it's stored only on the server. Until then, add sources by link or pasted text above.</p>
        ) : (
          <>
            <p className="mb-3 text-sm text-slate-600" data-testid="research-usage">Every Monday 4 topics are researched automatically. <b>{st.used_this_week}</b> of {st.weekly_cap} searches used this week (cap keeps costs predictable).</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. How UK cleaning firms win NHS or school contracts" data-testid="research-topic-input" />
              <Button onClick={() => run(topic)} disabled={busy || topic.length < 8 || !st.remaining} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="research-run-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Globe className="mr-2 h-4 w-4" />}{busy ? "Researching…" : "Research now"}</Button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">{st.topics.map((t, i) => <button key={i} disabled={busy || !st.remaining} onClick={() => run(t)} className="rounded-full border px-3 py-1 text-left text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50" data-testid={`research-topic-${i}`}>{t.split(" - ")[0]}</button>)}</div>
          </>
        )}
      </div>
    </Panel>
  );
};

export const Knowledge = () => {
  const [q, setQ] = useState("");
  const [f, setF] = useState({ q: "", topic: "" });
  const [items, reload] = useLoad("/admin/knowledge", f);
  const [st, reloadSt] = useLoad("/admin/knowledge/stats");
  const refresh = () => { reload(); reloadSt(); };
  return (
    <div className="grid gap-6" data-testid="manager-knowledge">
      {st && <p className="text-sm text-slate-600" data-testid="knowledge-stats"><b>{st.lessons}</b> lessons from <b>{st.sources}</b> sources the system has actually read. Verified/reported: {(st.by_evidence.verified || 0) + (st.by_evidence.reported || 0)} · claims/opinions: {(st.by_evidence.claim || 0) + (st.by_evidence.opinion || 0)} · flagged outdated: {st.outdated}. Live web search: {st.live_web_research}.</p>}
      <AddSource types={st?.source_types || ["web"]} onAdded={refresh} />
      <Research onDone={refresh} />
      <div className="flex flex-wrap gap-2">
        <form className="relative min-w-[220px] flex-1" onSubmit={(e) => { e.preventDefault(); setF({ ...f, q }); }}><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search lessons" className="pl-9" data-testid="knowledge-search-input" /></form>
        <Select value={f.topic || "all"} onValueChange={(x) => setF({ ...f, topic: x === "all" ? "" : x })}><SelectTrigger className="w-56" data-testid="knowledge-topic-select"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All topics</SelectItem>{(st?.topics || []).map((t) => <SelectItem key={t} value={t} className="capitalize">{label(t)}</SelectItem>)}</SelectContent></Select>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">{items?.map((k) => <Lesson key={k.id} k={k} onChange={refresh} />)}</div>
      {items?.length === 0 && <Empty>No lessons match.</Empty>}
    </div>
  );
};
