import { useCallback, useEffect, useRef, useState } from "react";
import { History } from "lucide-react";
import { toast } from "sonner";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, useLoad } from "@/components/admin/ui";
import { ChatList } from "@/components/manager/ChatList";
import { ChatThread } from "@/components/manager/ChatThread";
import { Composer } from "@/components/manager/Composer";
import { MemoryPanel } from "@/components/manager/MemoryPanel";
import { Priorities } from "@/components/manager/Priorities";
import { Alerts } from "@/components/manager/Alerts";
import { Approvals } from "@/components/manager/Approvals";
import { GrowthPlan } from "@/components/manager/GrowthPlan";
import { Knowledge } from "@/components/manager/Knowledge";
import { Reports } from "@/components/manager/Reports";
import { useManagerChat } from "@/hooks/useManagerChat";
import { useVoice, voiceSupport } from "@/hooks/useVoice";
import { api, errMsg } from "@/lib/api";

const STARTERS = ["What should I focus on this week?", "What is preventing my business from growing?", "How can I win 10 new commercial cleaning contracts?", "How far am I from £10,000 monthly profit?", "When should I hire another cleaner or a manager?", "How can I stop doing the cleaning myself?"];

function Assistant() {
  const [chats, setChats] = useState(null);
  const [query, setQuery] = useState("");
  const [sheet, setSheet] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [handsFree, setHandsFree] = useState(false);
  const [web, setWeb] = useState(false);
  const webRef = useRef(false);
  webRef.current = web;
  const [research] = useLoad("/admin/knowledge/research/status");
  const [saved, setSaved] = useState(new Set());
  const hf = useRef(false);
  hf.current = handsFree;
  const support = voiceSupport();
  const endRef = useRef(null);

  const loadChats = useCallback((q = query) => api.get("/admin/manager/chats", { params: { q } }).then((r) => setChats(r.data)).catch((e) => toast.error(errMsg(e))), [query]);
  const voiceRef = useRef(null);
  const onReply = useCallback((text, via) => { if (via === "voice") voiceRef.current.speak(text, () => hf.current && voiceRef.current.start(false)); }, []);
  const chat = useManagerChat({ onReply, webRef });
  const onTranscript = useCallback((t) => chat.send(t, "voice", () => loadChats()), [chat, loadChats]);
  const voice = useVoice({ onTranscript, onError: (m) => toast.error(m) });
  voiceRef.current = voice;

  useEffect(() => { loadChats(""); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.messages]);

  const open = (id) => { voice.stopSpeaking(); setSaved(new Set()); chat.open(id); setSheet(false); };
  const send = (t) => chat.send(t, "text", () => loadChats());
  const mic = () => {
    if (voice.state === "listening") return voice.stop();
    voice.stopSpeaking();
    voice.start(true);
  };
  const remember = async (s, i, k) => { try { await api.post("/admin/manager/memory", { kind: s.kind, text: s.text }); setSaved((x) => new Set(x).add(`${i}-${k}`)); toast.success("Saved to business memory"); } catch (e) { toast.error(errMsg(e)); } };
  const del = async () => {
    try { await api.delete(`/admin/manager/chats/${toDelete.id}`); if (toDelete.id === chat.chatId) chat.open(null); toast.success("Conversation deleted"); } catch (e) { toast.error(errMsg(e)); }
    setToDelete(null);
    loadChats();
  };
  const list = <ChatList chats={chats} activeId={chat.chatId} onOpen={open} onNew={() => open(null)} onDelete={setToDelete} onSearch={(q) => { setQuery(q); loadChats(q); }} />;

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]" data-testid="manager-assistant">
      <aside className="hidden lg:block lg:h-[calc(100vh-220px)]">{list}</aside>
      <section className="flex min-h-[60vh] min-w-0 flex-col">
        <button onClick={() => setSheet(true)} className="mb-3 flex items-center gap-2 self-start rounded-full border px-3 py-1.5 text-sm text-slate-600 lg:hidden" data-testid="manager-history-btn"><History className="h-4 w-4" />Conversations</button>
        <div className="flex-1 pb-4">
          {chat.messages.length === 0 ? (
            <div className="py-6" data-testid="manager-empty-state">
              <Alerts />
              <p className="font-display text-xl font-semibold text-slate-900">Hello - I'm your Business Manager.</p>
              <p className="mt-1 max-w-xl text-sm text-slate-500">I read your live bookings, enquiries, regular clients, reviews, costs and memory. I'll tell you what's actual, what's estimated and what's missing. Type or tap the mic.</p>
              <div className="mt-5 grid gap-2 sm:grid-cols-2">{STARTERS.map((s, i) => <button key={s} onClick={() => send(s)} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 transition-colors hover:border-[#8F7E22]" data-testid={`manager-starter-${i}`}>{s}</button>)}</div>
            </div>
          ) : <ChatThread messages={chat.messages} onSpeak={(t) => { voice.unlock(); voice.speak(t); }} onRemember={remember} saved={saved} />}
          <div ref={endRef} />
        </div>
        <Composer busy={chat.busy} web={web} setWeb={setWeb} research={research} thinking={chat.busy && chat.messages[chat.messages.length - 1]?.via === "voice"} voice={voice} support={support} handsFree={handsFree} setHandsFree={setHandsFree} onSend={send}
          onStop={() => { chat.stop(); voice.stopSpeaking(); }} onMic={mic} onVoiceStop={() => (voice.state === "speaking" ? voice.stopSpeaking() : voice.state === "idle" ? chat.stop() : voice.stop(true))} />
      </section>
      <Sheet open={sheet} onOpenChange={setSheet}><SheetContent side="left" className="w-[85vw] max-w-sm"><SheetHeader><SheetTitle>Conversations</SheetTitle></SheetHeader><div className="mt-4 h-[80vh]">{list}</div></SheetContent></Sheet>
      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete this conversation?</AlertDialogTitle><AlertDialogDescription>"{toDelete?.title}" will be permanently deleted. Saved business memory is not affected.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel data-testid="manager-delete-cancel-btn">Cancel</AlertDialogCancel><AlertDialogAction onClick={del} className="bg-red-600 hover:bg-red-700" data-testid="manager-delete-confirm-btn">Delete</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function BusinessManager() {
  return (
    <div data-testid="business-manager-page">
      <PageHeader eyebrow="Private · owner only" title="AI Business Manager" desc="Your business partner for operations, growth, marketing and finance - powered by your real dashboard data." />
      <Tabs defaultValue="assistant">
        <TabsList className="mb-6 h-auto w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="assistant" data-testid="manager-tab-assistant">Assistant</TabsTrigger>
          <TabsTrigger value="priorities" data-testid="manager-tab-priorities">My Business Priorities</TabsTrigger>
          <TabsTrigger value="growth" data-testid="manager-tab-growth">Goals & Roadmap</TabsTrigger>
          <TabsTrigger value="reports" data-testid="manager-tab-reports">Reports</TabsTrigger>
          <TabsTrigger value="approvals" data-testid="manager-tab-approvals">Approvals</TabsTrigger>
          <TabsTrigger value="knowledge" data-testid="manager-tab-knowledge">Industry knowledge</TabsTrigger>
          <TabsTrigger value="memory" data-testid="manager-tab-memory">Business memory</TabsTrigger>
        </TabsList>
        <TabsContent value="assistant"><Assistant /></TabsContent>
        <TabsContent value="priorities"><Priorities /></TabsContent>
        <TabsContent value="growth"><GrowthPlan /></TabsContent>
        <TabsContent value="reports"><Reports /></TabsContent>
        <TabsContent value="approvals"><Approvals /></TabsContent>
        <TabsContent value="knowledge"><Knowledge /></TabsContent>
        <TabsContent value="memory"><MemoryPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
