import { useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Notice, PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDateTime } from "@/lib/api";

function Audit({ reload }) {
  const [url, setUrl] = useState("https://");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/admin/tools/seo-audit", { url })).data); reload(); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Panel title="Technical SEO audit">
      <div className="flex gap-2"><Input value={url} onChange={(e) => setUrl(e.target.value)} className="max-w-lg font-mono" data-testid="seo-audit-url-input" />
        <Button onClick={run} disabled={busy} className="bg-slate-900 hover:bg-teal-700" data-testid="seo-audit-run-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Audit page</Button></div>
      {res && (
        <div className="mt-5" data-testid="seo-audit-result">
          <p className="font-mono text-4xl font-bold text-teal-700" data-testid="seo-audit-score">{res.score}/100</p>
          <ul className="mt-4 divide-y text-sm">{res.checks.map((c) => <li key={c.check} className="flex items-center justify-between gap-3 py-2"><span className="flex items-center gap-2">{c.ok ? <CheckCircle2 className="h-4 w-4 text-teal-600" /> : <XCircle className="h-4 w-4 text-red-500" />}{c.check}</span><span className="text-xs text-slate-500">{c.detail}</span></li>)}</ul>
        </div>
      )}
    </Panel>
  );
}

function Brief({ kind, reload }) {
  const [f, setF] = useState({ service: "End of tenancy cleaning", location: "" });
  const [res, setRes] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/admin/tools/brief", { ...f, kind })).data.content); reload(); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Panel title={kind === "seo" ? "AI keyword research & local landing page plan" : "AI Google Ads campaign builder"}>
      <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <Input placeholder="Service" value={f.service} onChange={(e) => setF({ ...f, service: e.target.value })} data-testid={`${kind}-service-input`} />
        <Input placeholder="Location, e.g. Croydon" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} data-testid={`${kind}-location-input`} />
        <Button onClick={run} disabled={busy || f.location.length < 2} className="bg-teal-600 hover:bg-teal-700" data-testid={`${kind}-generate-btn`}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Generate</Button>
      </div>
      {res && <pre className="mt-5 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-sans text-sm text-slate-700" data-testid={`${kind}-result`}>{res}</pre>}
    </Panel>
  );
}

export default function GrowthTools() {
  const [hist, reload] = useLoad("/admin/tools/history");
  return (
    <div data-testid="admin-growth-page">
      <PageHeader eyebrow="Growth" title="SEO & Google Ads" desc="Audit your website, plan local keywords and landing pages, and build profit-focused Google Ads campaigns with AI." />
      <Notice testid="growth-integration-notice">Live Google Ads, Search Console, Analytics and Business Profile data are <b>NOT CONNECTED YET</b> (each needs Google API approval / OAuth per company). Audits and AI plans below work now.</Notice>
      <Tabs defaultValue="seo">
        <TabsList><TabsTrigger value="seo" data-testid="growth-tab-seo">SEO</TabsTrigger><TabsTrigger value="ads" data-testid="growth-tab-ads">Google Ads</TabsTrigger><TabsTrigger value="history" data-testid="growth-tab-history">History</TabsTrigger></TabsList>
        <TabsContent value="seo" className="space-y-6"><Audit reload={reload} /><Brief kind="seo" reload={reload} /></TabsContent>
        <TabsContent value="ads"><Brief kind="ads" reload={reload} /></TabsContent>
        <TabsContent value="history">
          <Panel><ul className="divide-y text-sm">{hist?.map((h) => <li key={h.id} className="flex justify-between py-2"><span>{h.type.replace("_", " ")} · {h.url || `${h.service} – ${h.location}`}</span><span className="font-mono text-xs text-slate-400">{h.score != null ? `${h.score}/100 · ` : ""}{fmtDateTime(h.created_at)}</span></li>)}</ul></Panel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
