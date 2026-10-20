import { useCallback, useEffect, useRef, useState } from "react";
import { api, errMsg } from "@/lib/api";

const SILENT = "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQxAADB8AhSmxhIIEVCSiJrDCQBTcu3UrAIwUdkRgQbFAZC1CQEwTJ9mjRvBA4UOLD8nKVOWfh+UlK3z/177OXrfOdKl7pyn3Xf//WreyTRUoAWgBgkOAGbZHBgG1OF6zM82DWbZaUmMBptgQhGjsyYqc9ae9XFz280948NMBWInljyzsNRFLPWdnZGWrddDsjK1unuSrVN9jJsK8KuQtQCtMBjCEtImISdNKJOopIpBFpNSMbIHCSRpRR5iakjTiyzLhchUUBwCgyKiweBv/7UsQbg8isVNoMPMjAAAA0gAAABEVFGmgqK////9bP/6XCykxBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq";
const MIME = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac"];

export const voiceSupport = () => {
  if (typeof window === "undefined") return { ok: false, reason: "" };
  if (!window.isSecureContext) return { ok: false, reason: "Voice needs a secure (https) connection." };
  if (!navigator.mediaDevices?.getUserMedia) return { ok: false, reason: "This browser doesn't allow microphone access. Please type instead, or use Safari (iPhone) / Chrome." };
  if (!window.MediaRecorder) return { ok: false, reason: "This browser can't record audio. Please update iOS to 14.3+ or use a current Chrome/Safari, or type instead." };
  return { ok: true, reason: "" };
};

export function useVoice({ onTranscript, onError }) {
  const [state, setState] = useState("idle");
  const [level, setLevel] = useState(0);
  const r = useRef({ audio: null, stream: null, ctx: null, rec: null, timer: null, cancel: false });

  const unlock = () => {
    if (!r.current.audio) r.current.audio = new Audio();
    const a = r.current.audio;
    a.src = SILENT;
    a.play().catch(() => {});
  };

  const cleanupMeter = () => { clearInterval(r.current.timer); setLevel(0); };

  const transcribe = useCallback(async (blob, ext) => {
    setState("transcribing");
    try {
      const fd = new FormData();
      fd.append("file", blob, `speech.${ext}`);
      const { data } = await api.post("/admin/manager/transcribe", fd);
      setState("idle");
      onTranscript(data.text);
    } catch (e) { setState("idle"); onError(errMsg(e)); }
  }, [onTranscript, onError]);

  const start = useCallback(async (gesture = true) => {
    if (gesture) unlock();
    r.current.audio?.pause();
    try {
      if (!r.current.stream || !r.current.stream.active) r.current.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      onError(e?.name === "NotAllowedError" ? "Microphone permission was blocked. Allow microphone access for this site in your browser settings (iPhone: Settings > Safari > Microphone), or type instead." : "No microphone was found. Please type instead.");
      return;
    }
    const mime = MIME.find((m) => MediaRecorder.isTypeSupported?.(m)) || "";
    const rec = new MediaRecorder(r.current.stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    let heard = false;
    r.current.cancel = false;
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      cleanupMeter();
      const type = rec.mimeType || mime || "audio/webm";
      if (r.current.cancel || !heard) { setState("idle"); if (!r.current.cancel) onError("I didn't hear anything - tap the mic and speak, or type instead."); return; }
      transcribe(new Blob(chunks, { type }), type.includes("mp4") || type.includes("aac") ? "mp4" : "webm");
    };
    r.current.rec = rec;
    rec.start(250);
    setState("listening");
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!r.current.ctx && Ctx) r.current.ctx = new Ctx();
    const ctx = r.current.ctx;
    if (!ctx) { heard = true; return; }
    ctx.resume?.();
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    ctx.createMediaStreamSource(r.current.stream).connect(an);
    const buf = new Uint8Array(an.fftSize);
    const t0 = Date.now();
    let lastLoud = Date.now();
    r.current.timer = setInterval(() => {
      an.getByteTimeDomainData(buf);
      const rms = Math.sqrt(buf.reduce((s, v) => s + ((v - 128) / 128) ** 2, 0) / buf.length);
      setLevel(Math.min(1, rms * 8));
      if (rms > 0.03) { heard = true; lastLoud = Date.now(); }
      const quiet = Date.now() - lastLoud;
      if ((heard && quiet > 1600) || (!heard && Date.now() - t0 > 9000) || Date.now() - t0 > 90000) { if (rec.state === "recording") rec.stop(); }
    }, 100);
  }, [onError, transcribe]);

  const stop = useCallback((cancel = false) => {
    r.current.cancel = cancel;
    if (r.current.rec?.state === "recording") r.current.rec.stop();
  }, []);

  const speak = useCallback(async (text, onEnd) => {
    setState("speaking");
    try {
      const { data } = await api.post("/admin/manager/speak", { text }, { responseType: "blob" });
      if (!r.current.audio) r.current.audio = new Audio();
      const a = r.current.audio;
      a.src = URL.createObjectURL(data);
      a.onended = () => { setState("idle"); onEnd?.(); };
      await a.play();
    } catch (e) {
      setState("idle");
      onError(e?.name === "NotAllowedError" ? "Your browser blocked audio playback - tap the speaker icon on the reply to hear it." : "Voice playback failed - the written answer is shown.");
    }
  }, [onError]);

  const stopSpeaking = useCallback(() => { r.current.audio?.pause(); setState((s) => (s === "speaking" ? "idle" : s)); }, []);

  useEffect(() => () => {
    clearInterval(r.current.timer);
    r.current.audio?.pause();
    r.current.stream?.getTracks().forEach((t) => t.stop());
    r.current.ctx?.close?.();
  }, []);

  return { state, level, start, stop, speak, stopSpeaking, unlock };
}
