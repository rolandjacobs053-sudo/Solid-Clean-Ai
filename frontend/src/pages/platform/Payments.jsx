import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Empty, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { fmtDate, gbp } from "@/lib/api";

export default function Payments() {
  const [rows] = useLoad("/platform/payments");
  return (
    <div data-testid="platform-payments-page">
      <PageHeader eyebrow="Revenue" title="Subscription payments" desc="Stripe invoices for every company. Failed payments put the company into a 7-day grace period, then access is restricted until they pay." />
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["Date", "Company", "Amount due", "Paid", "Status", ""].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows?.map((r) => (
              <TableRow key={r.id} data-testid="payment-row">
                <TableCell>{fmtDate(r.created_at)}</TableCell><TableCell className="font-medium">{r.company_name}</TableCell>
                <TableCell className="font-mono">{gbp(r.amount_due)}</TableCell><TableCell className="font-mono">{gbp(r.amount_paid)}</TableCell>
                <TableCell><StatusBadge status={r.status} /></TableCell><TableCell>{r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-teal-700 hover:underline">Invoice</a>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {rows?.length === 0 && <Empty>No subscription payments yet.</Empty>}
      </div>
    </div>
  );
}
