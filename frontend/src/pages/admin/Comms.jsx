import { Fragment, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Empty, Notice, PageHeader, StatusBadge, useLoad } from "@/components/admin/ui";
import { fmtDateTime, label } from "@/lib/api";

const TEMPLATES = ["quote_sent", "enquiry_ack", "quote_follow_up", "booking_confirmation", "appointment_reminder", "feedback_review_request", "booking_cancelled", "owner_notification", "cold_outreach"];

export default function Comms() {
  const [template, setTemplate] = useState("");
  const [rows] = useLoad("/admin/comms", { template });
  const [open, setOpen] = useState(null);
  return (
    <div data-testid="admin-comms-page">
      <PageHeader eyebrow="Automation" title="Communications log" desc="Every automated email/SMS the system generated - acknowledgements, quotes, follow-ups, confirmations, reminders, review requests and owner alerts." />
      <Notice testid="comms-mocked-notice">Email &amp; SMS delivery is <b>SIMULATED</b>: messages are generated and logged here but not yet sent. Connect an email provider (e.g. Resend / Google Workspace) and SMS/WhatsApp (e.g. Twilio) to go live.</Notice>
      <Select value={template || "all"} onValueChange={(v) => setTemplate(v === "all" ? "" : v)}>
        <SelectTrigger className="mb-4 w-64 bg-white" data-testid="comms-template-filter"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="all">All message types</SelectItem>{TEMPLATES.map((t) => <SelectItem key={t} value={t}>{label(t)}</SelectItem>)}</SelectContent>
      </Select>
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <Table>
          <TableHeader><TableRow>{["Created", "Type", "Channel", "To", "Subject", "Status"].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows?.map((c) => (
              <Fragment key={c.id}>
                <TableRow className="cursor-pointer" onClick={() => setOpen(open === c.id ? null : c.id)} data-testid="comm-row">
                  <TableCell className="whitespace-nowrap font-mono text-xs">{fmtDateTime(c.created_at)}</TableCell>
                  <TableCell className="capitalize">{label(c.template)}</TableCell>
                  <TableCell className="uppercase text-xs">{c.channel}</TableCell>
                  <TableCell className="text-xs">{c.to}</TableCell>
                  <TableCell className="text-sm">{c.subject}</TableCell>
                  <TableCell><StatusBadge status={c.status} />{c.scheduled_for && <p className="mt-1 font-mono text-[10px] text-slate-400">{fmtDateTime(c.scheduled_for)}</p>}</TableCell>
                </TableRow>
                {open === c.id && <TableRow><TableCell colSpan={6} className="whitespace-pre-wrap bg-slate-50 text-sm text-slate-700" data-testid="comm-body">{c.body}</TableCell></TableRow>}
              </Fragment>
            ))}
          </TableBody>
        </Table>
        {rows?.length === 0 && <Empty>No messages yet.</Empty>}
      </div>
    </div>
  );
}
