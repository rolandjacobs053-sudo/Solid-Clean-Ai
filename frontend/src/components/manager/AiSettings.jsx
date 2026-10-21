import { useState } from "react";
import { Loader2, Play, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useLoad } from "@/components/admin/ui";
import { api, errMsg } from "@/lib/api";

export const ModelPicker = ({ value, onChange }) => {
  const [d] = useLoad("/admin/manager/models");
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-48 rounded-full text-xs" data-testid="manager-model-select"><SelectValue /></SelectTrigger>
      <SelectContent>{d?.models.map((m) => <SelectItem key={m.id} value={m.id} data-testid={`manager-model-${m.id}`}>{m.name}</SelectItem>)}</SelectContent>
    </Select>
  );
};

export const VoiceSettings = ({ voice }) => {
  const [p, setP] = useState(null);
  const [opts] = useLoad("/admin/manager/models");
  const [busy, setBusy] = useState(false);
  const load = async (o) => { if (o && !p) { try { setP((await api.get("/admin/manager/prefs")).data); } catch (e) { toast.error(errMsg(e)); } } };
  const save = async (next) => { setP(next); try { await api.put("/admin/manager/prefs", next); } catch (e) { toast.error(errMsg(e)); } };
  const preview = async () => { setBusy(true); voice.unlock(); await voice.speak("Hello, I'm your Solid Clean Business Manager. This is how I'll sound."); setBusy(false); };
  return (
    <Popover onOpenChange={load}>
      <PopoverTrigger asChild><button className="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs text-slate-600 hover:bg-white" data-testid="manager-voice-settings-btn"><Settings2 className="h-3.5 w-3.5" />Voice</button></PopoverTrigger>
      <PopoverContent className="w-72 space-y-3" data-testid="manager-voice-settings">
        {!p ? <Loader2 className="h-4 w-4 animate-spin" /> : <>
          <div className="space-y-1"><Label className="text-xs">Quality</Label>
            <Select value={p.tts_model} onValueChange={(v) => save({ ...p, tts_model: v })}><SelectTrigger data-testid="voice-model-select"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="tts-1-hd">HD (tts-1-hd) - clearer</SelectItem><SelectItem value="tts-1">Standard (tts-1) - faster</SelectItem></SelectContent></Select></div>
          <div className="space-y-1"><Label className="text-xs">Voice</Label>
            <Select value={p.voice} onValueChange={(v) => save({ ...p, voice: v })}><SelectTrigger data-testid="voice-voice-select"><SelectValue /></SelectTrigger>
              <SelectContent>{(opts?.voices || []).map((v) => <SelectItem key={v} value={v} className="capitalize">{v}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-2"><Label className="text-xs">Speed: {p.speed.toFixed(2)}x</Label>
            <Slider min={0.5} max={2} step={0.05} value={[p.speed]} onValueChange={([s]) => setP({ ...p, speed: s })} onValueCommit={([s]) => save({ ...p, speed: s })} data-testid="voice-speed-slider" /></div>
          <Button size="sm" variant="outline" onClick={preview} disabled={busy} data-testid="voice-preview-btn">{busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1 h-3.5 w-3.5" />}Preview voice</Button>
          <p className="text-[11px] text-slate-400">All voices are American-accented (OpenAI). Saved for every conversation.</p>
        </>}
      </PopoverContent>
    </Popover>
  );
};
