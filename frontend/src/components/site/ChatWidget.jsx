import { useEffect, useRef, useState } from "react";
import { MessageCircle, PhoneCall, Send, X } from "lucide-react";
import { toast } from "sonner";
import { API, api, errMsg } from "@/lib/api";
import { QuoteCard } from "@/components/site/QuoteCard";
import { useTenant } from "@/lib/tenant";

const strip = (t) => t.replace(/<<[\s\S]*?>>/g, "").replace(/<<[\s\S]*$/, "").trim();

function Escalate({ cid, pub, onDone }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post(`${pub}/chat/sessions/${cid}/escalate`, { name, phone, reason: "Customer asked to speak to a person" });
      onDone(data.message);
    } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <form onSubmit={submit} className="space-y-2 rounded-xl bg-amber-50 p-3" data-testid="chat-escalate-form">
      <p className="text-xs font-medium text-amber-900">Request a call back from our team</p>
      <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" data-testid="chat-escalate-name-input"
        className="w-full rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-teal-500" />
      <input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone number" data-testid="chat-escalate-phone-input"
        className="w-full rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-teal-500" />
      <button className="w-full rounded-full bg-slate-900 py-1.5 text-sm text-white hover:bg-teal-700" data-testid="chat-escalate-submit-btn">Call me back</button>
    </form>
  );
}

function Bubble({ m }) {
  if (m.role === "quote") return <QuoteCard quoteId={m.quote_id} result={m.result} />;
  const user = m.role === "user";
  const text = user ? m.text : strip(m.text);
  if (!text) return <div className="h-8 w-14 animate-pulse rounded-2xl bg-slate-100" />;
  return (
    <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${user ? "ml-auto bg-slate-900 text-white" : m.role === "notice" ? "bg-amber-50 text-amber-900" : "bg-slate-100 text-slate-800"}`}
      data-testid={`chat-message-${m.role}`}>{text}</div>
  );
}

export function ChatWidget() {
  const { slug, pub } = useTenant();
  const key = `sc_chat_${slug}`;
  const [open, setOpen] = useState(false);
  const [cid, setCid] = useState(sessionStorage.getItem(key));
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const end = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, escalating]);

  const start = async () => {
    setOpen(true);
    if (cid && msgs.length) return;
    const { data } = await api.post(`${pub}/chat/sessions`);
    sessionStorage.setItem(key, data.id);
    setCid(data.id);
    setMsgs([{ role: "assistant", text: data.greeting }]);
  };

  const push = (m) => setMsgs((prev) => [...prev, m]);
  const updateLast = (fn) => setMsgs((prev) => {
    const copy = [...prev];
    const i = copy.map((x) => x.role).lastIndexOf("assistant");
    copy[i] = { ...copy[i], text: fn(copy[i].text) };
    return copy;
  });

  const handle = (ev) => {
    if (ev.type === "delta") updateLast((t) => t + ev.text);
    else if (ev.type === "done") updateLast(() => ev.text);
    else if (ev.type === "quote") push({ role: "quote", quote_id: ev.quote_id, result: ev.result });
    else if (ev.type === "escalated") push({ role: "notice", text: "A member of our team has been notified and will call you back." });
    else if (ev.type === "error") updateLast(() => ev.text);
  };

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((prev) => [...prev, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      const res = await fetch(`${API}${pub}/chat/sessions/${cid}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        parts.filter((p) => p.startsWith("data: ")).forEach((p) => handle(JSON.parse(p.slice(6))));
      }
    } catch {
      updateLast(() => "Sorry, something went wrong. Please try again.");
    }
    setBusy(false);
  };

  if (!open)
    return (
      <button onClick={start} data-testid="ai-chat-toggle-btn"
        className="fixed bottom-24 right-4 z-50 flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3.5 text-sm font-medium text-white shadow-2xl shadow-teal-900/30 transition-transform hover:-translate-y-0.5 hover:bg-teal-700 md:bottom-6 md:right-6">
        <MessageCircle className="h-4 w-4" /> Ask our receptionist
      </button>
    );

  return (
    <div className="fixed bottom-4 right-4 z-50 flex h-[min(620px,calc(100vh-2rem))] w-[calc(100vw-2rem)] max-w-[400px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white/95 shadow-2xl backdrop-blur-xl rise" data-testid="ai-chat-panel">
      <div className="flex items-center justify-between bg-slate-900 px-5 py-4 text-white">
        <div>
          <p className="font-display text-sm font-semibold">Solid Clean receptionist</p>
          <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-teal-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />AI · prices from approved list</p>
        </div>
        <button onClick={() => setOpen(false)} className="rounded-full p-1.5 hover:bg-white/10" data-testid="ai-chat-close-btn"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4" data-testid="ai-chat-messages">
        {msgs.map((m, i) => <Bubble key={i} m={m} />)}
        {escalating && <Escalate cid={cid} pub={pub} onDone={(t) => { setEscalating(false); push({ role: "notice", text: t }); }} />}
        <div ref={end} />
      </div>
      <div className="border-t border-slate-100 p-3">
        <button onClick={() => setEscalating((v) => !v)} className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-teal-700" data-testid="ai-chat-escalate-btn">
          <PhoneCall className="h-3.5 w-3.5" /> Speak to a person instead
        </button>
        <form onSubmit={send} className="flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="e.g. End of tenancy for a 2-bed flat in SW19" data-testid="ai-chat-input"
            className="flex-1 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm outline-none focus:border-teal-500" />
          <button disabled={busy} className="grid h-10 w-10 place-items-center rounded-full bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50" data-testid="ai-chat-send-btn">
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
