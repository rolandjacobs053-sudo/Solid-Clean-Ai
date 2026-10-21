import { useState } from "react";
import { Check, Loader2, ScanSearch, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Empty, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDateTime, label } from "@/lib/api";

const Draft = ({ a, onDone }) => {
  const [v, setV] = useState({ subject: a.subject, body: a.body });
  const [busy, setBusy] = useState(false);
  const act = async (kind) => {
    setBusy(true);
    try {
      if (kind === "approve") { await api.patch(`/admin/strategy/approvals/${a.id}`, v); const { data } = await api.post(`/admin/strategy/approvals/${a.id}/approve`); toast[data.status === "sent" ? "success" : "error"](data.status === "sent" ? "Email sent" : `Not sent: ${label(data.status)}`); }
      else { await api.post(`/admin/strategy/approvals/${a.id}/reject`); toast.success("Draft rejected"); }
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
    onDone();
  };
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4" data-testid={`approval-${a.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500"><StatusBadge status={a.kind} /><span>To {a.name} &lt;{a.to}&gt;</span><span className="ml-auto font-mono">{fmtDateTime(a.created_at)}</span></div>
      <p className="mb-2 text-xs italic text-slate-500">{a.context}</p>
      <Input value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} className="mb-2 font-medium" data-testid={`approval-subject-${a.id}`} />
      <Textarea rows={6} value={v.body} onChange={(e) => setV({ ...v, body: e.target.value })} data-testid={`approval-body-${a.id}`} />
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={() => act("approve")} disabled={busy} className="bg-[#023F00] hover:bg-[#012b00]" data-testid={`approval-approve-${a.id}`}>{busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Check className="mr-1 h-3.5 w-3.5" />}Approve & send</Button>
        <Button size="sm" variant="ghost" onClick={() => act("reject")} disabled={busy} data-testid={`approval-reject-${a.id}`}><X className="mr-1 h-3.5 w-3.5" />Reject</Button>
      </div>
    </article>
  );
};

export const Approvals = () => {
  const [list, reload] = useLoad("/admin/strategy/approvals", { status: "pending" });
  const [sent, reloadSent] = useLoad("/admin/strategy/approvals", { status: "sent" });
  const [busy, setBusy] = useState(false);
  const scan = async () => { setBusy(true); try { const { data } = await api.post("/admin/strategy/approvals/scan"); toast.success(data.created ? `${data.created} new drafts ready for review` : "Nothing needs a follow-up right now"); reload(); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  const done = () => { reload(); reloadSent(); };
  return (
    <div className="max-w-3xl" data-testid="manager-approvals">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-lg text-sm text-slate-600">The AI drafts quote follow-ups, review requests and commercial prospect follow-ups. Nothing is sent until you tap Approve. Opted-out contacts are skipped automatically.</p>
        <Button onClick={scan} disabled={busy} className="rounded-full bg-[#8F7E22] hover:bg-[#7a6b1d]" data-testid="approvals-scan-btn">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ScanSearch className="mr-2 h-4 w-4" />}Find follow-ups</Button>
      </div>
      <div className="space-y-4">{list?.map((a) => <Draft key={a.id} a={a} onDone={done} />)}</div>
      {list?.length === 0 && <Empty>Nothing waiting for approval.</Empty>}
      {sent?.length > 0 && <details className="mt-6"><summary className="cursor-pointer text-sm text-slate-600">Sent ({sent.length})</summary><ul className="mt-2 space-y-1 text-sm">{sent.map((a) => <li key={a.id} className="text-slate-600">{fmtDateTime(a.approved_at)} · {label(a.kind)} · {a.to} · {a.subject}</li>)}</ul></details>}
    </div>
  );
};
