import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, BookmarkPlus, Mic, Volume2 } from "lucide-react";

const Thinking = () => (
  <span className="inline-flex items-center gap-1.5 text-sm text-slate-500" data-testid="manager-thinking-indicator">
    {[0, 150, 300].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-[#8F7E22]" style={{ animationDelay: `${d}ms` }} />)}
    <span className="ml-1">Thinking…</span>
  </span>
);

const Bubble = ({ m, i, onSpeak, onRemember, saved }) => {
  const mine = m.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`manager-msg-${i}`}>
      <div className={`max-w-[92%] rounded-2xl px-4 py-3 sm:max-w-[80%] ${mine ? "bg-[#023F00] text-white" : "border border-slate-200 bg-white text-slate-800"}`}>
        {m.via === "voice" && <p className={`mb-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider ${mine ? "text-[#d9c56a]" : "text-[#8F7E22]"}`}><Mic className="h-3 w-3" />{mine ? "You said" : "Spoken reply"}</p>}
        {mine ? <p className="whitespace-pre-wrap text-sm">{m.text}</p> : m.pending && !m.text ? <Thinking /> : (
          <div className="md-body" data-testid={`manager-msg-text-${i}`}><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown></div>
        )}
        {m.stopped && <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-slate-400" data-testid={`manager-msg-stopped-${i}`}>Stopped</p>}
        {m.error && <p className="mt-2 flex items-start gap-1.5 text-xs text-red-600" data-testid={`manager-msg-error-${i}`}><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{typeof m.error === "string" ? m.error : "This reply failed. Please try again."}</p>}
        {!mine && !m.pending && m.text && (
          <div className="mt-2 flex flex-wrap gap-2">
            <button onClick={() => onSpeak(m.text)} className="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50" data-testid={`manager-msg-speak-${i}`}><Volume2 className="h-3.5 w-3.5" />Read aloud</button>
            {m.suggestions?.map((s, k) => (
              <button key={k} onClick={() => onRemember(s, i, k)} disabled={saved.has(`${i}-${k}`)} className="flex items-center gap-1 rounded-full border border-[#8F7E22]/40 bg-[#8F7E22]/5 px-2.5 py-1 text-left text-xs text-[#5c5116] disabled:opacity-60" data-testid={`manager-msg-remember-${i}-${k}`}>
                <BookmarkPlus className="h-3.5 w-3.5 shrink-0" />{saved.has(`${i}-${k}`) ? "Saved to memory" : `Remember: ${s.text}`}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const ChatThread = ({ messages, onSpeak, onRemember, saved }) => (
  <div className="space-y-4" data-testid="manager-thread">
    {messages.map((m, i) => <Bubble key={i} m={m} i={i} onSpeak={onSpeak} onRemember={onRemember} saved={saved} />)}
  </div>
);
