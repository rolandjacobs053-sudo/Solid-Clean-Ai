import { useState } from "react";
import { Pencil, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Empty, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate } from "@/lib/api";

const KINDS = ["target", "fact", "decision", "project", "preference"];

const Editor = ({ init = { kind: "target", text: "" }, onSave, testid }) => {
  const [v, setV] = useState(init);
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Select value={v.kind} onValueChange={(kind) => setV({ ...v, kind })}>
        <SelectTrigger className="sm:w-36" data-testid={`${testid}-kind`}><SelectValue /></SelectTrigger>
        <SelectContent>{KINDS.map((k) => <SelectItem key={k} value={k} className="capitalize">{k}</SelectItem>)}</SelectContent>
      </Select>
      <Input value={v.text} onChange={(e) => setV({ ...v, text: e.target.value })} placeholder="e.g. Target: £10,000 monthly profit by end of 2027" className="flex-1" data-testid={`${testid}-text`} />
      <Button onClick={() => v.text.trim().length > 1 && onSave(v, () => setV({ kind: v.kind, text: "" }))} className="bg-[#023F00] hover:bg-[#012b00]" data-testid={`${testid}-save`}><Save className="mr-1 h-4 w-4" />Save</Button>
    </div>
  );
};

export const MemoryPanel = () => {
  const [items, reload] = useLoad("/admin/manager/memory");
  const [editing, setEditing] = useState(null);
  const add = async (v, reset) => { try { await api.post("/admin/manager/memory", v); reset(); reload(); toast.success("Saved to business memory"); } catch (e) { toast.error(errMsg(e)); } };
  const edit = async (id, v) => { try { await api.put(`/admin/manager/memory/${id}`, v); setEditing(null); reload(); toast.success("Memory updated"); } catch (e) { toast.error(errMsg(e)); } };
  const del = async (id) => { await api.delete(`/admin/manager/memory/${id}`); reload(); };
  return (
    <div className="max-w-3xl" data-testid="manager-memory">
      <p className="mb-4 text-sm text-slate-600">Targets, decisions, projects and facts the Business Manager uses in every conversation. Correct or delete anything outdated. This is private and never shared with the customer chat on your website.</p>
      <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-4"><p className="mb-2 flex items-center gap-1 text-sm font-semibold"><Plus className="h-4 w-4" />Add to memory</p><Editor onSave={add} testid="memory-new" /></div>
      {items?.length === 0 && <Empty>Nothing saved yet.</Empty>}
      <ul className="space-y-2">
        {items?.map((m) => (
          <li key={m.id} className="rounded-xl border border-slate-200 bg-white p-3" data-testid={`memory-item-${m.id}`}>
            {editing === m.id ? <Editor init={{ kind: m.kind, text: m.text }} onSave={(v) => edit(m.id, v)} testid={`memory-edit-${m.id}`} /> : (
              <div className="flex items-start gap-3">
                <span className="mt-0.5 rounded-full bg-[#8F7E22]/10 px-2 py-0.5 font-mono text-[10px] uppercase text-[#5c5116]">{m.kind}</span>
                <p className="flex-1 text-sm text-slate-800">{m.text}<span className="ml-2 font-mono text-[10px] text-slate-400">{fmtDate(m.updated_at)}</span></p>
                <button onClick={() => setEditing(m.id)} className="text-slate-400 hover:text-slate-700" aria-label="Edit" data-testid={`memory-edit-btn-${m.id}`}><Pencil className="h-4 w-4" /></button>
                <button onClick={() => del(m.id)} className="text-slate-400 hover:text-red-600" aria-label="Delete" data-testid={`memory-delete-btn-${m.id}`}><Trash2 className="h-4 w-4" /></button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};
