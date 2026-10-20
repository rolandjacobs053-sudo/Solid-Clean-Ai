import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader2, Plus, Sparkles, Star } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DemoTag, Empty, Kpi, Notice, PageHeader, Panel, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate } from "@/lib/api";

const Stars = ({ n }) => <span className="flex">{[1, 2, 3, 4, 5].map((i) => <Star key={i} className={`h-4 w-4 ${i <= n ? "fill-amber-400 text-amber-400" : "text-slate-200"}`} />)}</span>;

function AddReview({ open, setOpen, onDone }) {
  const [f, setF] = useState({ author: "", rating: 5, text: "", platform: "google", review_date: new Date().toISOString().slice(0, 10) });
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post("/admin/reviews", { ...f, rating: Number(f.rating) }); toast.success("Review logged"); setOpen(false); onDone(); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="add-review-dialog">
        <DialogHeader><DialogTitle>Log a review</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <Input required placeholder="Reviewer name" value={f.author} onChange={(e) => setF({ ...f, author: e.target.value })} data-testid="add-review-author-input" />
          <Input type="number" min={1} max={5} value={f.rating} onChange={(e) => setF({ ...f, rating: e.target.value })} data-testid="add-review-rating-input" />
          <Input type="date" value={f.review_date} onChange={(e) => setF({ ...f, review_date: e.target.value })} />
          <Textarea placeholder="Review text" value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} data-testid="add-review-text-input" />
          <Button className="bg-teal-600 hover:bg-teal-700" data-testid="add-review-submit-btn">Save</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ReviewCard({ r, reload }) {
  const [resp, setResp] = useState(r.response || "");
  const [busy, setBusy] = useState(false);
  const draft = async () => {
    setBusy(true);
    try { setResp((await api.post(`/admin/reviews/${r.id}/draft`)).data.response); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const approve = async () => { await api.patch(`/admin/reviews/${r.id}`, { response: resp, status: "approved" }); toast.success("Reply approved - post it on Google Business Profile"); reload(); };
  const hide = async (hidden) => {
    const hidden_reason = hidden ? window.prompt("Why are you hiding this review? (only for offensive, fake or off-topic content - not for negative reviews)") : "";
    if (hidden && !hidden_reason) return;
    await api.patch(`/admin/reviews/${r.id}`, { hidden, hidden_reason }); toast.success(hidden ? "Hidden from the website" : "Shown on the website"); reload();
  };
  const web = r.source === "customer_feedback";
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="review-card">
      <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-3"><Stars n={r.rating} /><span className="font-medium">{r.author}</span><DemoTag show={r.demo} /></div><div className="flex items-center gap-2"><span className="font-mono text-xs text-slate-400">{fmtDate(r.review_date)}</span><StatusBadge status={r.status} /></div></div>
      <p className="mt-3 text-sm text-slate-600">{r.text}</p>
      {web && <p className="mt-2 font-mono text-[11px] text-slate-500" data-testid={`review-web-status-${r.id}`}>Verified customer · {r.service_name} · {!r.publish_consent ? "Private feedback (no consent to publish)" : r.hidden ? `Hidden from website: ${r.hidden_reason}` : "Shown on your website"}</p>}
      <Textarea className="mt-4" rows={3} placeholder="Your public reply" value={resp} onChange={(e) => setResp(e.target.value)} data-testid={`review-response-input-${r.id}`} />
      <div className="mt-2 flex gap-2">
        <Button size="sm" variant="outline" onClick={draft} disabled={busy} data-testid={`review-draft-btn-${r.id}`}>{busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Sparkles className="mr-1 h-4 w-4" />}Draft with AI</Button>
        <Button size="sm" disabled={!resp} onClick={approve} className="bg-teal-600 hover:bg-teal-700" data-testid="crm-review-approve-btn">Approve reply</Button>
        {web && r.publish_consent && <Button size="sm" variant="ghost" onClick={() => hide(!r.hidden)} data-testid={`review-hide-btn-${r.id}`}>{r.hidden ? "Show on website" : "Hide from website"}</Button>}
      </div>
    </div>
  );
}

export default function Reviews() {
  const [data, reload] = useLoad("/admin/reviews");
  const [adding, setAdding] = useState(false);
  if (!data) return <p className="font-mono text-sm">Loading…</p>;
  const s = data.stats;
  return (
    <div data-testid="admin-reviews-page">
      <PageHeader eyebrow="Reputation" title="Reviews" desc="Every completed job gets a 'How did we do?' email - no filtering of unhappy customers. Reviews customers agree to share appear on your website automatically; UK law doesn't allow hiding genuine negative reviews or publishing invented ones. Replies are AI-drafted and only published after your approval.">
        <Button onClick={() => setAdding(true)} className="bg-slate-900 hover:bg-teal-700" data-testid="reviews-add-btn"><Plus className="mr-1 h-4 w-4" />Log review</Button>
      </PageHeader>
      <Notice testid="reviews-gbp-notice">Google Business Profile sync is <b>NOT CONNECTED YET</b> (needs GBP API approval). Log reviews manually for now.</Notice>
      <div className="grid gap-4 md:grid-cols-4">
        <Kpi testid="reviews-kpi-count" label="Reviews" value={s.count} />
        <Kpi testid="reviews-kpi-average" label="Average rating" value={s.average ?? "—"} accent />
        <Kpi testid="reviews-kpi-attention" label="Need attention" value={s.needs_attention} />
        <Panel className="md:col-span-1"><div className="h-20"><ResponsiveContainer><LineChart data={s.trend}><XAxis dataKey="month" hide /><YAxis domain={[1, 5]} hide /><Tooltip /><Line dataKey="avg" stroke="#0D9488" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div></Panel>
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">{data.reviews.map((r) => <ReviewCard key={r.id} r={r} reload={reload} />)}</div>
      {data.reviews.length === 0 && <Empty>No reviews logged.</Empty>}
      <AddReview open={adding} setOpen={setAdding} onDone={reload} />
    </div>
  );
}
