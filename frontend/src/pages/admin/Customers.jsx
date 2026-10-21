import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Search, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Empty, PageHeader, Panel, useLoad } from "@/components/admin/ui";
import { CustomerForm, EMPTY_CUSTOMER } from "@/components/customers/CustomerForm";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";

export default function Customers() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [list] = useLoad("/admin/customers", { q: search });
  const [settings] = useLoad("/admin/settings");
  const [open, setOpen] = useState(false);
  const [v, setV] = useState(EMPTY_CUSTOMER);
  const nav = useNavigate();
  const create = async () => {
    try { const { data } = await api.post("/admin/customers", v); toast.success("Customer created"); setOpen(false); setV(EMPTY_CUSTOMER); nav(`/admin/customers/${data.id}`); }
    catch (e) {
      const d = e?.response?.data?.detail;
      if (d?.existing_id) { toast.error(d.message, { action: { label: "Open", onClick: () => nav(`/admin/customers/${d.existing_id}`) } }); } else toast.error(errMsg(e));
    }
  };
  return (
    <div data-testid="customers-page">
      <PageHeader eyebrow="Customer management" title="Customers" desc="Every customer in one place - website bookings and the ones you add by phone, email or WhatsApp.">
        <Button onClick={() => setOpen(true)} className="rounded-full bg-[#023F00] hover:bg-[#012b00]" data-testid="customer-new-btn"><Plus className="mr-2 h-4 w-4" />New customer</Button>
      </PageHeader>
      <form className="relative mb-4 max-w-md" onSubmit={(e) => { e.preventDefault(); setSearch(q); }}>
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => { setQ(e.target.value); if (!e.target.value) setSearch(""); }} placeholder="Search name, phone, email or postcode" className="pl-9" data-testid="customer-search-input" />
      </form>
      <Panel>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm" data-testid="customers-table">
            <thead><tr className="text-left font-mono text-[10px] uppercase tracking-wider text-slate-500"><th className="pb-2">Customer</th><th>Contact</th><th>Postcode</th><th>Bookings</th><th>Upcoming</th><th>Paid total</th><th>Last booking</th></tr></thead>
            <tbody>
              {list?.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`customer-row-${c.id}`}>
                  <td className="py-2.5"><Link to={`/admin/customers/${c.id}`} className="flex items-center gap-2 font-medium text-slate-900 hover:underline" data-testid={`customer-link-${c.id}`}><UserRound className="h-4 w-4 text-slate-400" />{c.name}</Link>{c.demo && <span className="ml-6 rounded bg-slate-900 px-1 font-mono text-[9px] text-white">DEMO</span>}</td>
                  <td className="text-xs text-slate-600">{c.phone}<br />{c.email}</td>
                  <td className="font-mono text-xs">{c.postcode}</td>
                  <td className="font-mono">{c.stats.bookings}</td>
                  <td className="font-mono">{c.stats.upcoming}</td>
                  <td className="font-mono">{gbp(c.stats.spend)}</td>
                  <td className="font-mono text-xs">{c.stats.last_date ? fmtDate(c.stats.last_date) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {list?.length === 0 && <Empty>No customers match.</Empty>}
      </Panel>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto"><DialogHeader><DialogTitle>New customer profile</DialogTitle></DialogHeader>
          <CustomerForm v={v} set={setV} services={settings?.pricing?.services || []} />
          <DialogFooter><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={create} disabled={v.name.trim().length < 2} className="bg-[#023F00] hover:bg-[#012b00]" data-testid="customer-create-btn">Create customer</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
