import { useEffect, useState } from "react";
import { Loader2, PhoneCall, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { DemoTag, Empty, Notice, PageHeader, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDateTime, gbp } from "@/lib/api";

function PhoneLine() {
  const [v] = useLoad("/admin/voice/status");
  if (!v) return null;
  return (
    <Notice testid="receptionist-phone-notice">
      <PhoneCall className="mr-2 inline h-4 w-4" />
      {v.configured && v.voice_number
        ? <>Phone answering is <b>LIVE</b> on {v.voice_number}. Calls appear below with full transcripts.</>
        : <>Phone answering is <b>NOT CONNECTED YET</b>. {v.configured ? "Add your Twilio number in Settings → Business (voice_number)." : "Twilio credentials are needed."}</>}
      <span className="mt-1 block font-mono text-[11px]" data-testid="receptionist-webhook-url">Twilio “A call comes in” webhook (HTTP POST): {v.webhook_url}</span>
    </Notice>
  );
}

function Detail({ id, reload }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/admin/conversations/${id}`).then((r) => setD(r.data));
  useEffect(() => { setD(null); load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const summarise = async () => {
    setBusy(true);
    try { await api.post(`/admin/conversations/${id}/summarise`); await load(); reload(); toast.success("Summary saved to CRM"); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const resolve = async () => { await api.patch(`/admin/conversations/${id}/resolve`); toast.success("Marked as resolved"); load(); reload(); };
  if (!d) return <p className="font-mono text-sm">Loading…</p>;
  const c = d.conversation;
  return (
    <div data-testid="conversation-detail">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={c.status} />{c.escalated && <span className="text-xs text-red-700">Escalated: {c.escalation_reason}</span>}
      </div>
      <div className="mt-4 rounded-xl bg-teal-50 p-4 text-sm text-teal-900" data-testid="conversation-summary">{c.summary || "No summary yet."}</div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="outline" onClick={summarise} disabled={busy} data-testid="conversation-summarise-btn">{busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Sparkles className="mr-1 h-4 w-4" />}Generate summary</Button>
        {c.status !== "resolved" && <Button size="sm" variant="outline" onClick={resolve} data-testid="conversation-resolve-btn">Mark resolved</Button>}
      </div>
      {d.quotes.length > 0 && <div className="mt-4 space-y-1">{d.quotes.map((q) => <p key={q.id} className="text-xs text-slate-600">Quote: {q.service_name} · <b className="font-mono">{gbp(q.total)}</b> · {q.status}</p>)}</div>}
      <div className="mt-5 max-h-[55vh] space-y-2 overflow-y-auto">
        {c.messages.map((m, i) => (
          <div key={i} className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${m.role === "user" ? "ml-auto bg-slate-900 text-white" : m.role === "system" ? "mx-auto bg-amber-50 font-mono text-[11px] text-amber-900" : "bg-slate-100"}`}>{m.text}</div>
        ))}
      </div>
    </div>
  );
}

export default function Conversations() {
  const [rows, reload] = useLoad("/admin/conversations");
  const [sel, setSel] = useState(null);
  return (
    <div data-testid="admin-conversations-page">
      <PageHeader eyebrow="AI receptionist" title="Conversations & call summaries" desc="Web chat and phone calls share the same brain: your knowledge base, price list and policies." />
      <PhoneLine />
      <div className="grid gap-6 lg:grid-cols-5">
        <Panel title="Recent" className="lg:col-span-2">
          <ul className="space-y-2" data-testid="conversation-list">
            {rows?.map((c) => (
              <li key={c.id}>
                <button onClick={() => setSel(c.id)} className={`w-full rounded-xl border p-3 text-left transition-colors ${sel === c.id ? "border-teal-600 bg-teal-50" : "border-slate-200 hover:border-teal-300"}`} data-testid="conversation-row">
                  <div className="flex items-center justify-between"><span className="font-mono text-[10px] text-slate-500">{fmtDateTime(c.updated_at)} · {c.channel}<DemoTag show={c.demo} /></span><StatusBadge status={c.status} /></div>
                  <p className="mt-1 line-clamp-2 text-sm">{c.summary || c.last_message || "No messages yet"}</p>
                </button>
              </li>
            ))}
            {rows?.length === 0 && <Empty>No conversations yet - try the chat on the public site.</Empty>}
          </ul>
        </Panel>
        <Panel title="Transcript" className="lg:col-span-3">{sel ? <Detail id={sel} reload={reload} /> : <Empty>Select a conversation.</Empty>}</Panel>
      </div>
    </div>
  );
}
