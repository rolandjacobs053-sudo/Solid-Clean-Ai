import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { API, api, errMsg } from "@/lib/api";

const readError = async (res) => {
  try { const j = await res.json(); return typeof j.detail === "string" ? j.detail : "Request failed"; } catch { return `Request failed (${res.status})`; }
};

export function useManagerChat({ onReply, webRef }) {
  const [chatId, setChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("claude-sonnet-5-5");
  const ctrl = useRef(null);

  const patchLast = (fn) => setMessages((m) => m.map((x, i) => (i === m.length - 1 ? fn(x) : x)));

  const open = useCallback(async (id) => {
    ctrl.current?.abort();
    if (!id) { setChatId(null); setMessages([]); return; }
    try { const { data } = await api.get(`/admin/manager/chats/${id}`); setChatId(id); setMessages(data.messages); setModel(data.model || "claude-sonnet-5-5"); } catch (e) { toast.error(errMsg(e)); }
  }, []);

  const changeModel = useCallback(async (m) => {
    setModel(m);
    if (chatId) { try { await api.patch(`/admin/manager/chats/${chatId}`, { model: m }); } catch (e) { toast.error(errMsg(e)); } }
  }, [chatId]);

  const send = useCallback(async (text, via, onCreated) => {
    let id = chatId;
    if (!id) {
      try { id = (await api.post("/admin/manager/chats", { model })).data.id; setChatId(id); } catch (e) { toast.error(errMsg(e)); return; }
    }
    setMessages((m) => [...m, { role: "user", text, via, web: !!webRef?.current }, { role: "assistant", text: "", via, pending: true }]);
    setBusy(true);
    ctrl.current = new AbortController();
    let full = "";
    try {
      const res = await fetch(`${API}/admin/manager/chats/${id}/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, via, web: !!webRef?.current }), signal: ctrl.current.signal });
      if (!res.ok) throw new Error(await readError(res));
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          if (!p.startsWith("data: ")) continue;
          const ev = JSON.parse(p.slice(6));
          if (ev.type === "delta") { full += ev.text; patchLast((x) => ({ ...x, text: full.replace(/<<REMEMBER[\s\S]*$/, "") })); }
          else if (ev.type === "memory_suggestion") patchLast((x) => ({ ...x, suggestions: [...(x.suggestions || []), ev] }));
          else if (ev.type === "done") { patchLast((x) => ({ ...x, text: ev.text, pending: false })); onReply?.(ev.text, via); }
          else if (ev.type === "error") { patchLast((x) => ({ ...x, pending: false, error: ev.text })); toast.error(ev.text); }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") patchLast((x) => ({ ...x, pending: false, stopped: true }));
      else { const msg = e.message === "Failed to fetch" ? "Connection lost - check your internet and try again." : e.message; patchLast((x) => ({ ...x, pending: false, error: msg })); toast.error(msg); }
    } finally {
      setBusy(false);
      onCreated?.();
    }
  }, [chatId, onReply, webRef, model]);

  const stop = useCallback(() => ctrl.current?.abort(), []);
  return { chatId, messages, busy, open, send, stop, model, changeModel };
}
