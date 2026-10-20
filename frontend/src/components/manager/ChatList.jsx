import { useState } from "react";
import { MessageSquarePlus, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtDateTime } from "@/lib/api";

export const ChatList = ({ chats, activeId, onOpen, onNew, onDelete, onSearch }) => {
  const [q, setQ] = useState("");
  return (
    <div className="flex h-full flex-col" data-testid="manager-chat-list">
      <Button onClick={onNew} className="w-full rounded-full bg-[#023F00] hover:bg-[#012b00]" data-testid="manager-new-chat-btn"><MessageSquarePlus className="mr-2 h-4 w-4" />New conversation</Button>
      <form className="relative mt-3" onSubmit={(e) => { e.preventDefault(); onSearch(q); }}>
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => { setQ(e.target.value); if (!e.target.value) onSearch(""); }} placeholder="Search conversations" className="pl-9" data-testid="manager-chat-search-input" />
      </form>
      <ul className="mt-3 flex-1 space-y-1 overflow-y-auto">
        {chats?.map((c) => (
          <li key={c.id} className={`group flex items-center gap-2 rounded-xl px-3 py-2 transition-colors ${c.id === activeId ? "bg-[#023F00]/10" : "hover:bg-slate-100"}`}>
            <button className="min-w-0 flex-1 text-left" onClick={() => onOpen(c.id)} data-testid={`manager-chat-item-${c.id}`}>
              <p className="truncate text-sm font-medium text-slate-800">{c.title}</p>
              <p className="font-mono text-[10px] text-slate-400">{fmtDateTime(c.updated_at)}</p>
            </button>
            <button onClick={() => onDelete(c)} className="rounded p-1 text-slate-400 opacity-100 hover:text-red-600 lg:opacity-0 lg:group-hover:opacity-100" aria-label="Delete conversation" data-testid={`manager-chat-delete-${c.id}`}><Trash2 className="h-4 w-4" /></button>
          </li>
        ))}
        {chats?.length === 0 && <p className="px-3 py-6 text-center text-xs text-slate-400" data-testid="manager-chat-list-empty">No conversations yet.</p>}
      </ul>
    </div>
  );
};
