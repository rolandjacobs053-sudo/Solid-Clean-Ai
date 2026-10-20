import { useRef } from "react";
import { Camera, ImageOff, Loader2, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";

const MAX = 10;
const MAX_MB = 10;

function Thumb({ p, onRemove, onReplace, onBroken }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-50" data-testid="photo-thumb">
      <div className="relative aspect-square">
        {p.broken ? <ImageOff className="absolute inset-0 m-auto h-6 w-6 text-slate-300" /> : <img src={p.preview} alt={p.name} className="h-full w-full object-cover" onError={() => onBroken()} />}
      </div>
      {p.status === "uploading" && <div className="absolute inset-0 flex items-center justify-center bg-white/70"><Loader2 className="h-6 w-6 animate-spin text-slate-700" /></div>}
      {p.status === "error" && <div className="absolute inset-x-0 bottom-0 bg-red-600/90 p-1.5 text-[11px] leading-tight text-white" data-testid="photo-upload-error">{p.error}</div>}
      <div className="absolute right-1.5 top-1.5 flex gap-1">
        <button type="button" onClick={onReplace} className="rounded-full bg-white/90 p-1.5 shadow hover:bg-white" aria-label="Replace photo" data-testid="photo-replace-btn"><RefreshCw className="h-3.5 w-3.5" /></button>
        <button type="button" onClick={onRemove} className="rounded-full bg-white/90 p-1.5 shadow hover:bg-white" aria-label="Remove photo" data-testid="photo-remove-btn"><X className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  );
}

export function PhotoUploader({ pub, photos, setPhotos, title = "Upload Photos of Your Property", text = "Please upload clear photographs of your property and any areas that may require additional attention. This helps Solid Clean Ltd understand the property’s condition and assess the cleaning work required." }) {
  const input = useRef();
  const replacing = useRef(null);
  const update = (local, patch) => setPhotos((list) => list.map((x) => (x.local === local ? { ...x, ...patch } : x)));
  const remove = (local) => setPhotos((list) => { const x = list.find((p) => p.local === local); if (x) URL.revokeObjectURL(x.preview); return list.filter((p) => p.local !== local); });

  const upload = async (file, at) => {
    const local = Math.random().toString(36).slice(2);
    const item = { local, preview: URL.createObjectURL(file), name: file.name, status: "uploading" };
    setPhotos((list) => {
      if (!at) return [...list, item];
      const i = list.findIndex((x) => x.local === at);
      if (i >= 0) URL.revokeObjectURL(list[i].preview);
      return i < 0 ? [...list, item] : list.map((x, j) => (j === i ? item : x));
    });
    if (file.size > MAX_MB * 1024 * 1024) return update(local, { status: "error", error: `Larger than ${MAX_MB} MB` });
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post(`${pub}/photos`, fd);
      update(local, { status: "done", id: data.id, token: data.token });
    } catch (e) { update(local, { status: "error", error: errMsg(e) }); toast.error(`${file.name}: ${errMsg(e)}`); }
  };

  const onFiles = (files) => {
    const list = [...files];
    const at = replacing.current;
    replacing.current = null;
    input.current.value = "";
    if (!list.length) return;
    if (at) { upload(list[0], at); list.shift(); }
    const room = MAX - photos.length;
    if (list.length > room) toast.error(`You can upload up to ${MAX} photos.`);
    list.slice(0, Math.max(room, 0)).forEach((f) => upload(f));
  };
  const pick = (at) => {
    replacing.current = at;
    const reset = () => { setTimeout(() => { if (!input.current?.files?.length) replacing.current = null; }, 500); window.removeEventListener("focus", reset); };
    window.addEventListener("focus", reset);
    input.current.click();
  };

  return (
    <div data-testid="photo-upload-section">
      <h2 className="font-display text-2xl font-bold text-slate-900">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">{text}</p>
      <input ref={input} type="file" accept="image/*,.heic,.heif" multiple hidden onChange={(e) => onFiles(e.target.files)} data-testid="photo-file-input" />
      <button type="button" onClick={() => pick(null)} disabled={photos.length >= MAX}
        className="mt-5 flex w-full flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-slate-300 bg-white px-6 py-10 text-center transition-colors hover:border-[#8F7E22] hover:bg-[#8F7E22]/5 disabled:opacity-50" data-testid="photo-add-btn">
        <Camera className="h-8 w-8 text-[#023F00]" />
        <span className="font-semibold text-slate-900">{photos.length ? "Add more photos" : "Take or choose photos"}</span>
        <span className="text-xs text-slate-500">From your phone, tablet or computer · JPG, PNG, WEBP or HEIC · up to {MAX} photos, {MAX_MB} MB each</span>
      </button>
      {photos.length > 0 && (
        <div className="mt-5 grid grid-cols-3 gap-3 sm:grid-cols-5" data-testid="photo-preview-grid">
          {photos.map((p) => <Thumb key={p.local} p={p} onRemove={() => remove(p.local)} onReplace={() => pick(p.local)} onBroken={() => update(p.local, { broken: true })} />)}
        </div>
      )}
      <p className="mt-4 text-xs text-slate-500" data-testid="photo-count">{photos.filter((p) => p.status === "done").length} photo(s) uploaded. Photos are optional - you can continue without them. They are only seen by the Solid Clean team.</p>
      {photos.some((p) => p.status === "error") && <Button type="button" variant="ghost" size="sm" className="mt-2 text-red-700" onClick={() => setPhotos((l) => l.filter((p) => p.status !== "error"))} data-testid="photo-clear-errors-btn">Remove failed uploads</Button>}
    </div>
  );
}
