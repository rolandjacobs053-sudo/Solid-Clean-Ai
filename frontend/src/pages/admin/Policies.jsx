import { useEffect, useState } from "react";
import { AlertTriangle, History } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fmtDate, fmtDateTime } from "@/lib/api";

function Editor({ p, owner, reload }) {
  const [d, setD] = useState(p);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { setD(p); setConfirm(false); }, [p]);
  const save = async () => { try { await api.put(`/admin/policies/${p.key}`, { title: d.title, draft_content: d.draft_content, needs_review: d.needs_review, effective_date: d.effective_date, require_acceptance: d.require_acceptance }); toast.success("Draft saved"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const publish = async () => { try { await save(); const { data } = await api.post(`/admin/policies/${p.key}/publish`, { confirm: true }); toast.success(`Published version ${data.version}`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const markers = (d.draft_content.match(/\[REVIEW REQUIRED[^\]]*\]/g) || []).length;
  return (
    <div className="space-y-4" data-testid="policy-editor">
      <div className="flex flex-wrap items-center gap-3">
        <Input value={d.title} disabled={!owner} onChange={(e) => setD({ ...d, title: e.target.value })} className="max-w-md font-display font-semibold" data-testid="policy-title-input" />
        <StatusBadge status={p.published_version ? `published_v${p.published_version}` : "draft"} />
        {d.needs_review && <span className="flex items-center gap-1 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />Needs your review</span>}
      </div>
      <Textarea rows={14} value={d.draft_content} disabled={!owner} onChange={(e) => setD({ ...d, draft_content: e.target.value })} data-testid="policy-content-input" />
      {markers > 0 && <p className="text-xs text-amber-700" data-testid="policy-review-markers">{markers} [REVIEW REQUIRED] marker(s) must be replaced with your approved wording before publishing.</p>}
      <div className="flex flex-wrap items-end gap-4">
        <div><Label className="text-xs">Effective date</Label><Input type="date" disabled={!owner} value={d.effective_date || ""} onChange={(e) => setD({ ...d, effective_date: e.target.value })} className="mt-1" /></div>
        {p.audience === "public" && <label className="flex items-center gap-2 text-sm">Customers must accept when booking<Switch disabled={!owner} checked={d.require_acceptance} onCheckedChange={(v) => setD({ ...d, require_acceptance: v })} data-testid="policy-require-switch" /></label>}
      </div>
      {owner && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={save} data-testid="policy-save-btn">Save draft</Button>
          {confirm
            ? <Button onClick={publish} className="bg-teal-600 hover:bg-teal-700" data-testid="policy-publish-confirm-btn">Confirm: publish as version {p.published_version + 1}</Button>
            : <Button onClick={() => setConfirm(true)} className="bg-slate-900 hover:bg-teal-700" data-testid="policy-publish-btn">Publish…</Button>}
        </div>
      )}
      <p className="text-xs text-slate-500">Publishing creates a new version. Customers who already booked keep the version they accepted.</p>
      {p.versions?.length > 0 && (
        <Panel title={<span className="flex items-center gap-2"><History className="h-4 w-4" />Version history</span>}>
          <ul className="space-y-2 text-xs" data-testid="policy-versions">{[...p.versions].reverse().map((v) => (
            <li key={v.version} className="rounded-lg bg-slate-50 p-3"><b>v{v.version}</b> · effective {fmtDate(v.effective_date)} · published {fmtDateTime(v.published_at)} by {v.published_by}<p className="mt-1 line-clamp-2 text-slate-500">{v.content}</p></li>
          ))}</ul>
        </Panel>
      )}
    </div>
  );
}

export default function Policies() {
  const { user } = useAuth();
  const [rows, reload] = useLoad("/admin/policies");
  const [sel, setSel] = useState("booking");
  const current = rows?.find((p) => p.key === sel) || rows?.[0];
  return (
    <div data-testid="admin-policies-page">
      <PageHeader eyebrow="Compliance" title="Policies & terms" desc="Drafts were prepared only from facts you've stated (full payment upfront, 24-hour notice, 3-day End of Tenancy guarantee). Anything that needs your decision is marked [REVIEW REQUIRED] - nothing is published until you approve it." />
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Panel>
          <ul className="space-y-1" data-testid="policy-list">
            {rows?.map((p) => (
              <li key={p.key}><button onClick={() => setSel(p.key)} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${current?.key === p.key ? "bg-teal-50 text-teal-900" : "hover:bg-slate-50"}`} data-testid={`policy-item-${p.key}`}>
                <span>{p.title}{p.audience === "staff" && <span className="ml-1 text-[10px] text-slate-400">(staff)</span>}</span>
                <span className={`h-2 w-2 rounded-full ${p.published_version ? "bg-teal-500" : "bg-amber-400"}`} />
              </button></li>
            ))}
          </ul>
        </Panel>
        {current && <Panel><Editor p={current} owner={user.role === "owner"} reload={reload} /></Panel>}
      </div>
    </div>
  );
}
