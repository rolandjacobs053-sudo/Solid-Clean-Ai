import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Loader2, Square, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Empty, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDateTime } from "@/lib/api";

const chunks = (t) => {
  const plain = t.replace(/\|/g, " ").replace(/[#*_`>-]{1,}/g, " ").replace(/\s+/g, " ").trim();
  const out = [];
  let cur = "";
  plain.split(/(?<=[.!?])\s+/).forEach((s) => { if ((cur + s).length > 3500) { out.push(cur); cur = ""; } cur += `${s} `; });
  if (cur.trim()) out.push(cur);
  return out;
};

const Listen = ({ text }) => {
  const [state, setState] = useState("idle");
  const audio = useRef(null);
  const stop = useRef(false);
  const play = async () => {
    if (state !== "idle") { stop.current = true; audio.current?.pause(); setState("idle"); return; }
    stop.current = false;
    audio.current = audio.current || new Audio();
    audio.current.play().catch(() => {});
    setState("loading");
    try {
      for (const c of chunks(text)) {
        if (stop.current) break;
        const { data } = await api.post("/admin/manager/speak", { text: c }, { responseType: "blob" });
        if (stop.current) break;
        audio.current.src = URL.createObjectURL(data);
        setState("playing");
        await audio.current.play();
        await new Promise((r) => { audio.current.onended = r; audio.current.onpause = r; });
      }
    } catch { toast.error("Couldn't play the report aloud. Please try again."); }
    setState("idle");
  };
  return <Button size="sm" variant="outline" onClick={play} data-testid="report-listen-btn">{state === "loading" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : state === "playing" ? <Square className="mr-1 h-3.5 w-3.5" /> : <Volume2 className="mr-1 h-3.5 w-3.5" />}{state === "idle" ? "Listen" : "Stop"}</Button>;
};

export const Reports = () => {
  const [list, reload] = useLoad("/admin/strategy/reports");
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState("");
  const gen = async (kind) => {
    setBusy(kind);
    try {
      await api.post("/admin/strategy/reports/generate", { kind });
      for (let i = 0; i < 45; i += 1) {
        await new Promise((r) => setTimeout(r, 3000));
        const { data } = await api.get(`/admin/strategy/jobs/report_${kind}`);
        if (data.status === "done") { setOpen((await api.get(`/admin/strategy/reports/${data.result_id}`)).data); reload(); break; }
        if (data.status === "failed") { toast.error(data.error); break; }
        if (i === 44) toast.message("Still working - check back in a few minutes.");
      }
    } catch (e) { toast.error(errMsg(e)); }
    setBusy("");
  };
  const view = async (id) => { try { setOpen((await api.get(`/admin/strategy/reports/${id}`)).data); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]" data-testid="manager-reports">
      <div>
        <p className="mb-3 text-sm text-slate-600">A daily brief arrives at 6:30am and a weekly review every Monday at 7am (UK time) once the site is published. You can also create one now.</p>
        <div className="mb-4 flex flex-wrap gap-2">{["daily", "weekly", "monthly"].map((k) => <Button key={k} size="sm" variant="outline" disabled={!!busy} onClick={() => gen(k)} data-testid={`report-generate-${k}`}>{busy === k && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}New {k}</Button>)}</div>
        <ul className="space-y-1">{list?.map((r) => <li key={r.id}><button onClick={() => view(r.id)} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-100 ${open?.id === r.id ? "bg-slate-100" : ""}`} data-testid={`report-item-${r.id}`}><FileText className="h-4 w-4 shrink-0 text-slate-400" /><span className="min-w-0 flex-1 truncate">{r.title}</span></button></li>)}</ul>
        {list?.length === 0 && <Empty>No reports yet.</Empty>}
      </div>
      <article className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5" data-testid="report-view">
        {open ? <><div className="mb-3 flex items-center justify-between gap-2"><p className="font-mono text-[11px] text-slate-400">{fmtDateTime(open.created_at)}</p><Listen key={open.id} text={open.body} /></div><div className="md-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{open.body}</ReactMarkdown></div></> : <Empty>{busy ? "Writing your report from live data…" : "Pick or create a report."}</Empty>}
      </article>
    </div>
  );
};
