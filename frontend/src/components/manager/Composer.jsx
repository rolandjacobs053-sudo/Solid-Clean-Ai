import { useState } from "react";
import { Loader2, Mic, Send, Square, VolumeX } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const LABEL = { listening: "Listening… pause when you're done", transcribing: "Turning your speech into text…", thinking: "Thinking about your question…", speaking: "Speaking - tap stop or the mic to interrupt" };

const VoiceBar = ({ state, level, onStop }) => (
  <div className="mb-2 flex items-center justify-between gap-3 rounded-xl bg-[#023F00] px-4 py-2.5 text-sm text-white" data-testid="manager-voice-status" data-state={state}>
    <span className="flex items-center gap-2">
      {state === "listening" && <span className="flex h-4 items-end gap-0.5">{[0.6, 1, 0.8, 0.5].map((f, i) => <span key={i} className="w-1 rounded bg-[#d9c56a] transition-all" style={{ height: `${Math.max(15, level * f * 100)}%` }} />)}</span>}
      {(state === "transcribing" || state === "thinking") && <Loader2 className="h-4 w-4 animate-spin" />}
      {state === "speaking" && <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#d9c56a]" />}
      {LABEL[state]}
    </span>
    {state !== "transcribing" && <button onClick={onStop} className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold hover:bg-white/25" data-testid="manager-voice-stop-btn">{state === "speaking" ? <span className="flex items-center gap-1"><VolumeX className="h-3.5 w-3.5" />Stop speaking</span> : state === "thinking" ? "Stop" : "Cancel"}</button>}
  </div>
);

export const Composer = ({ busy, thinking, voice, support, handsFree, setHandsFree, onSend, onStop, onMic, onVoiceStop }) => {
  const [text, setText] = useState("");
  const submit = () => { if (!text.trim() || busy) return; onSend(text.trim()); setText(""); };
  const vs = voice.state === "idle" && thinking ? "thinking" : voice.state;
  return (
    <div className="sticky bottom-0 z-10 border-t border-slate-200 bg-[#f6f7f9]/95 pb-3 pt-3 backdrop-blur" data-testid="manager-composer">
      {vs !== "idle" && <VoiceBar state={vs} level={voice.level} onStop={onVoiceStop} />}
      <div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 focus-within:border-[#8F7E22]">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          rows={2} placeholder="Ask anything about your business…" className="min-h-[56px] flex-1 resize-none border-0 text-base shadow-none focus-visible:ring-0" data-testid="manager-input" />
        <button onClick={onMic} disabled={!support.ok || vs === "transcribing" || busy} title={support.ok ? "Speak" : support.reason}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors disabled:opacity-40 ${vs === "listening" ? "animate-pulse bg-red-600 text-white" : "bg-[#8F7E22] text-white hover:bg-[#7a6b1d]"}`} aria-label="Speak" data-testid="manager-mic-btn"><Mic className="h-5 w-5" /></button>
        {busy
          ? <button onClick={onStop} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white" aria-label="Stop response" data-testid="manager-stop-btn"><Square className="h-4 w-4 fill-current" /></button>
          : <button onClick={submit} disabled={!text.trim()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#023F00] text-white disabled:opacity-40" aria-label="Send" data-testid="manager-send-btn"><Send className="h-5 w-5" /></button>}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-500">
        {support.ok
          ? <label className="flex items-center gap-2"><Switch checked={handsFree} onCheckedChange={setHandsFree} data-testid="manager-handsfree-switch" />Hands-free: keep listening after each spoken reply</label>
          : <span className="text-amber-700" data-testid="manager-voice-unsupported">Voice unavailable: {support.reason}</span>}
        <span>Drafts and advice only - nothing is sent or changed without you.</span>
      </div>
    </div>
  );
};
