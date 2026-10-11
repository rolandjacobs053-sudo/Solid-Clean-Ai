import { useState } from "react";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { DemoTag, Empty, Notice, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, label } from "@/lib/api";

const SECTORS = ["letting_agent", "estate_agent", "property_management", "landlord", "airbnb_management", "office", "gym", "construction"];
const STATUSES = ["to_contact", "contacted", "replied", "interested", "meeting", "proposal", "won", "not_interested", "opted_out"];

function AddProspect({ open, setOpen, onDone }) {
  const [f, setF] = useState({ company: "", sector: "letting_agent", contact_name: "", email: "", phone: "", area: "", website: "", notes: "", consent: false });
  const submit = async (e) => {
    e.preventDefault();
    try { const { data } = await api.post("/admin/prospects", f); toast.success(data.status === "opted_out" ? "Added - but this email is on the suppression list" : "Prospect added"); setOpen(false); onDone(); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="add-prospect-dialog">
        <DialogHeader><DialogTitle>Add commercial prospect</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          {["company", "contact_name", "email", "phone", "area", "website"].map((k) => <Input key={k} required={k === "company"} placeholder={label(k)} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`add-prospect-${k}-input`} />)}
          <Select value={f.sector} onValueChange={(v) => setF({ ...f, sector: v })}>
            <SelectTrigger data-testid="add-prospect-sector-select"><SelectValue /></SelectTrigger>
            <SelectContent>{SECTORS.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
          </Select>
          <Textarea placeholder="Research notes for personalisation" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
          {f.sector === "landlord" && <label className="flex items-center gap-2 text-sm"><Checkbox checked={f.consent} onCheckedChange={(c) => setF({ ...f, consent: !!c })} />Individual has given consent to marketing emails</label>}
          <Button className="bg-teal-600 hover:bg-teal-700" data-testid="add-prospect-submit-btn">Save</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Compose({ p, onClose, onDone }) {
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    setBusy(true);
    try { setDraft((await api.post(`/admin/prospects/${p.id}/draft`)).data); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const send = async () => {
    try { await api.post(`/admin/prospects/${p.id}/send`, { ...draft, origin_url: window.location.origin }); toast.success("Email queued (simulated) with unsubscribe link"); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl" data-testid="compose-dialog">
        <DialogHeader><DialogTitle>Email {p.company}</DialogTitle></DialogHeader>
        {!draft ? (
          <Button onClick={generate} disabled={busy} className="bg-slate-900 hover:bg-teal-700" data-testid="compose-generate-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}Draft personalised email with AI</Button>
        ) : (
          <div className="grid gap-3">
            <p className="font-mono text-xs text-slate-500">Step {draft.step} of 3 · review before sending</p>
            <Input value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} data-testid="compose-subject-input" />
            <Textarea rows={10} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} data-testid="compose-body-input" />
            <Button onClick={send} className="bg-teal-600 hover:bg-teal-700" data-testid="compose-send-btn">Approve &amp; send</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function LogReply({ p, onClose, onDone }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/admin/prospects/${p.id}/classify-reply`, { text }); toast.success(`Reply classified: ${label(data.category)}`); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="reply-dialog">
        <DialogHeader><DialogTitle>Log reply from {p.company}</DialogTitle></DialogHeader>
        <Textarea rows={6} placeholder="Paste their reply" value={text} onChange={(e) => setText(e.target.value)} data-testid="reply-text-input" />
        <Button onClick={submit} disabled={busy || !text} className="bg-slate-900 hover:bg-teal-700" data-testid="reply-classify-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Classify with AI</Button>
      </DialogContent>
    </Dialog>
  );
}

function Suppressions() {
  const [rows, reload] = useLoad("/admin/suppressions");
  const [email, setEmail] = useState("");
  const add = async () => { try { await api.post("/admin/suppressions", { email }); setEmail(""); toast.success("Added to suppression list"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex gap-2"><Input placeholder="email@company.co.uk" value={email} onChange={(e) => setEmail(e.target.value)} className="max-w-sm" data-testid="suppression-email-input" /><Button onClick={add} data-testid="suppression-add-btn">Add</Button></div>
      <ul className="divide-y text-sm" data-testid="suppression-list">{rows?.map((r) => <li key={r.id} className="flex justify-between py-2"><span className="font-mono">{r.email}</span><span className="text-xs text-slate-500">{label(r.reason)} · {fmtDate(r.created_at)}</span></li>)}</ul>
      {rows?.length === 0 && <Empty>No opt-outs yet.</Empty>}
    </div>
  );
}

export default function Outreach() {
  const [sector, setSector] = useState("");
  const [rows, reload] = useLoad("/admin/prospects", { sector });
  const [adding, setAdding] = useState(false);
  const [compose, setCompose] = useState(null);
  const [reply, setReply] = useState(null);
  const setStatus = async (p, status) => { await api.patch(`/admin/prospects/${p.id}`, { status }); reload(); };

  return (
    <div data-testid="admin-outreach-page">
      <PageHeader eyebrow="Business development" title="Commercial outreach" desc="Prospect database, AI-personalised sequences, reply categorisation and opt-out enforcement.">
        <Button onClick={() => setAdding(true)} className="bg-slate-900 hover:bg-teal-700" data-testid="outreach-add-btn"><Plus className="mr-1 h-4 w-4" />Add prospect</Button>
      </PageHeader>
      <Notice testid="outreach-compliance-notice">UK PECR/GDPR: B2B emails to corporate addresses use legitimate interests with a clear opt-out; sole traders and individual landlords need consent. Suppressed contacts are blocked automatically. Sending is <b>SIMULATED</b> until a sending domain/provider is connected; email verification is format-only for now.</Notice>
      <Tabs defaultValue="prospects">
        <TabsList><TabsTrigger value="prospects" data-testid="outreach-tab-prospects">Prospects</TabsTrigger><TabsTrigger value="suppressions" data-testid="outreach-tab-suppressions">Suppression list</TabsTrigger></TabsList>
        <TabsContent value="prospects">
          <Select value={sector || "all"} onValueChange={(v) => setSector(v === "all" ? "" : v)}>
            <SelectTrigger className="my-3 w-56 bg-white" data-testid="outreach-sector-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All sectors</SelectItem>{SECTORS.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
          </Select>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <Table>
              <TableHeader><TableRow>{["Company", "Sector", "Contact", "Email check", "Steps", "Status", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {rows?.map((p) => (
                  <TableRow key={p.id} data-testid="prospect-row">
                    <TableCell className="font-medium">{p.company}<DemoTag show={p.demo} /><p className="text-xs font-normal text-slate-500">{p.area}</p></TableCell>
                    <TableCell className="capitalize">{label(p.sector)}</TableCell>
                    <TableCell className="text-xs">{p.contact_name}<br />{p.email}</TableCell>
                    <TableCell className="font-mono text-[11px]">{label(p.email_check)}</TableCell>
                    <TableCell className="font-mono">{p.steps_sent}/3</TableCell>
                    <TableCell>
                      <Select value={p.status} onValueChange={(v) => setStatus(p, v)}>
                        <SelectTrigger className="h-8 w-36 border-0 p-0 shadow-none" data-testid={`prospect-status-${p.id}`}><StatusBadge status={p.status} /></SelectTrigger>
                        <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="flex gap-2">
                      <Button size="sm" variant="outline" disabled={p.status === "opted_out"} onClick={() => setCompose(p)} data-testid={`prospect-email-btn-${p.id}`}>Email</Button>
                      <Button size="sm" variant="ghost" onClick={() => setReply(p)} data-testid={`prospect-reply-btn-${p.id}`}>Log reply</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {rows?.length === 0 && <Empty>No prospects yet.</Empty>}
          </div>
        </TabsContent>
        <TabsContent value="suppressions"><Suppressions /></TabsContent>
      </Tabs>
      <AddProspect open={adding} setOpen={setAdding} onDone={reload} />
      {compose && <Compose p={compose} onClose={() => setCompose(null)} onDone={reload} />}
      {reply && <LogReply p={reply} onClose={() => setReply(null)} onDone={reload} />}
    </div>
  );
}
