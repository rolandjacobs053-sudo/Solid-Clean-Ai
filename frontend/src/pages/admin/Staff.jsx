import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fmtDate } from "@/lib/api";

export default function Staff() {
  const { user } = useAuth();
  const [rows, reload] = useLoad("/admin/staff");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", email: "", password: "", job_role: "Cleaner", phone: "" });
  const owner = user.role === "owner";
  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/admin/staff", f); toast.success("Team member added - share their login details securely"); setOpen(false); reload(); } catch (err) { toast.error(errMsg(err)); }
  };
  const toggle = async (u, active) => { try { await api.patch(`/admin/staff/${u.id}`, { active }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div data-testid="admin-staff-page">
      <PageHeader eyebrow="Team" title="Employees & users" desc="Add cleaners, managers and office staff. Each gets their own login to this company's workspace; jobs can be assigned in Bookings.">
        {owner && <Button onClick={() => setOpen(true)} className="bg-slate-900 hover:bg-teal-700" data-testid="staff-add-btn"><Plus className="mr-1 h-4 w-4" />Add team member</Button>}
      </PageHeader>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["Name", "Email", "Role", "Phone", "Access", "Added", "Active"].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows?.map((u) => (
              <TableRow key={u.id} data-testid="staff-row">
                <TableCell className="font-medium">{u.name}</TableCell><TableCell className="text-xs">{u.email}</TableCell><TableCell>{u.job_role}</TableCell>
                <TableCell className="text-xs">{u.phone || "—"}</TableCell><TableCell><StatusBadge status={u.role} /></TableCell><TableCell className="text-xs">{fmtDate(u.created_at)}</TableCell>
                <TableCell><Switch checked={u.active !== false} disabled={!owner || u.role === "owner"} onCheckedChange={(v) => toggle(u, v)} data-testid={`staff-active-${u.id}`} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="staff-dialog">
          <DialogHeader><DialogTitle>Add team member</DialogTitle></DialogHeader>
          <form onSubmit={add} className="grid gap-3">
            {[["name", "Full name"], ["email", "Email"], ["password", "Temporary password (8+)"], ["job_role", "Job role (e.g. Cleaner, Manager)"], ["phone", "Phone"]].map(([k, l]) => (
              <Input key={k} placeholder={l} required={["name", "email", "password"].includes(k)} type={k === "password" ? "password" : "text"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`staff-${k}-input`} />
            ))}
            <Button className="bg-teal-600 hover:bg-teal-700" data-testid="staff-submit-btn">Add</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
