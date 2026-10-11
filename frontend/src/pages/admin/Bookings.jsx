import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DemoTag, Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { api, errMsg, fmtDate, gbp } from "@/lib/api";

function Actions({ b, reload }) {
  const [confirming, setConfirming] = useState(false);
  const patch = async (status) => {
    try {
      await api.patch(`/admin/bookings/${b.id}`, { status });
      toast.success(status === "completed" ? "Job completed - feedback & review request sent" : "Booking cancelled - approve any refund in Stripe");
      reload();
    } catch (e) { toast.error(errMsg(e)); }
  };
  if (b.status !== "confirmed") return null;
  return (
    <div className="flex gap-2">
      <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={() => patch("completed")} data-testid={`booking-complete-btn-${b.id}`}>Mark complete</Button>
      {confirming
        ? <Button size="sm" variant="destructive" onClick={() => patch("cancelled")} data-testid={`booking-cancel-confirm-btn-${b.id}`}>Confirm cancel</Button>
        : <Button size="sm" variant="outline" onClick={() => setConfirming(true)} data-testid={`booking-cancel-btn-${b.id}`}>Cancel</Button>}
    </div>
  );
}

function Assign({ b, staff, reload }) {
  const set = async (v) => { try { await api.patch(`/admin/bookings/${b.id}`, { assigned_to: v === "none" ? "" : v }); toast.success("Job assigned"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Select value={b.assigned_to || "none"} onValueChange={set}>
      <SelectTrigger className="h-8 w-36" data-testid={`booking-assign-${b.id}`}><SelectValue /></SelectTrigger>
      <SelectContent><SelectItem value="none">Unassigned</SelectItem>{staff?.filter((s) => s.active !== false).map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
    </Select>
  );
}

export default function Bookings() {
  const [status, setStatus] = useState("confirmed");
  const [rows, reload] = useLoad("/admin/bookings", { status: status === "all" ? "" : status });
  const [staff] = useLoad("/admin/staff");
  return (
    <div data-testid="admin-bookings-page">
      <PageHeader eyebrow="Operations" title="Bookings & jobs" desc="Bookings are confirmed only after payment. Completing a job triggers a feedback and review request to every customer." />
      <Tabs value={status} onValueChange={setStatus} className="mb-4">
        <TabsList className="flex-wrap">
          {[["confirmed", "Upcoming"], ["completed", "Completed"], ["pending_payment", "Awaiting payment"], ["cancelled", "Cancelled"], ["all", "All"]].map(([v, t]) => (
            <TabsTrigger key={v} value={v} data-testid={`bookings-tab-${v}`}>{t}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["When", "Customer", "Service", "Postcode", "Total", "Payment", "Status", "Assigned", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows?.map((b) => (
              <TableRow key={b.id} data-testid="booking-row">
                <TableCell className="whitespace-nowrap font-mono text-xs">{fmtDate(b.date)} · {b.slot}</TableCell>
                <TableCell className="font-medium">{b.customer.name}<DemoTag show={b.demo} /><p className="text-xs font-normal text-slate-500">{b.customer.phone}</p></TableCell>
                <TableCell className="text-sm">{b.service_name}{b.access_notes && <p className="text-xs text-slate-500">{b.access_notes}</p>}</TableCell>
                <TableCell className="font-mono text-xs">{b.postcode}</TableCell>
                <TableCell className="font-mono">{gbp(b.total)}</TableCell>
                <TableCell><StatusBadge status={b.payment_status} /></TableCell>
                <TableCell><StatusBadge status={b.status} testid={`booking-status-${b.id}`} /></TableCell>
                <TableCell><Assign b={b} staff={staff} reload={reload} /></TableCell>
                <TableCell><Actions b={b} reload={reload} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {rows?.length === 0 && <Empty>No bookings here.</Empty>}
      </div>
    </div>
  );
}
