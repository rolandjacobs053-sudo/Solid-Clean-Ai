import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Clock, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BookingDetail } from "@/components/admin/BookingDetail";
import { DemoTag, PageHeader, useLoad } from "@/components/admin/ui";
import { useAuth } from "@/context/AuthContext";
import { api, fmtDate } from "@/lib/api";

const COLORS = ["#0F766E", "#B45309", "#7C3AED", "#BE123C", "#1D4ED8", "#4D7C0F", "#C2410C"];
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const monday = (d) => { const x = new Date(d); x.setHours(12, 0, 0, 0); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const VISIBLE = ["confirmed", "completed"];

function JobCard({ b, color, onOpen }) {
  return (
    <button onClick={() => onOpen(b)} className="w-full rounded-xl border border-slate-200 bg-white p-3 text-left transition-transform hover:-translate-y-0.5 hover:shadow-md" style={{ borderLeft: `4px solid ${color}` }} data-testid={`schedule-job-${b.id}`}>
      <p className="flex items-center gap-1 font-mono text-xs font-semibold text-slate-900"><Clock className="h-3 w-3" />{b.slot}{b.status === "completed" && <span className="ml-auto text-[10px] text-emerald-700">DONE</span>}</p>
      <p className="mt-1 text-sm font-medium leading-tight">{b.service_name}</p>
      <p className="mt-1 truncate text-xs text-slate-500">{b.customer.name}<DemoTag show={b.demo} /></p>
      <p className="mt-1 flex items-center gap-1 font-mono text-[10px] text-slate-500"><MapPin className="h-3 w-3" />{b.postcode}</p>
      <p className="mt-2 truncate font-mono text-[10px] font-semibold uppercase" style={{ color }} data-testid={`schedule-job-assignee-${b.id}`}>{b.assigned_name || "Unassigned"}</p>
    </button>
  );
}

function useStaff(enabled) {
  const [staff, setStaff] = useState([]);
  useEffect(() => { if (enabled) api.get("/admin/staff").then((r) => setStaff(r.data)).catch(() => {}); }, [enabled]);
  return staff;
}

export default function Schedule() {
  const { user } = useAuth();
  const isStaff = user.role === "staff";
  const [start, setStart] = useState(() => monday(new Date()));
  const [who, setWho] = useState("all");
  const [open, setOpen] = useState(null);
  const days = useMemo(() => [...Array(7)].map((_, i) => addDays(start, i)), [start]);
  const [rows] = useLoad("/admin/bookings", { date_from: iso(days[0]), date_to: iso(days[6]) });
  const staff = useStaff(!isStaff);
  const color = (id) => (id ? COLORS[Math.max(0, staff.findIndex((s) => s.id === id)) % COLORS.length] : "#94A3B8");
  const jobs = (rows || []).filter((b) => VISIBLE.includes(b.status) && (who === "all" || (who === "none" ? !b.assigned_to : b.assigned_to === who)));
  const today = iso(new Date());
  return (
    <div data-testid="admin-schedule-page">
      <PageHeader eyebrow="Operations" title={isStaff ? "My schedule" : "Staff schedule"} desc={isStaff ? "Your assigned jobs for the week." : "Weekly view of every confirmed job and who is cleaning it. Assign cleaners from the Bookings page."}>
        <div className="flex flex-wrap items-center gap-2">
          {!isStaff && (
            <Select value={who} onValueChange={setWho}>
              <SelectTrigger className="w-44" data-testid="schedule-staff-filter"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">All cleaners</SelectItem><SelectItem value="none">Unassigned</SelectItem>{staff.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          )}
          <Button variant="outline" size="icon" onClick={() => setStart(addDays(start, -7))} data-testid="schedule-prev-week"><ChevronLeft className="h-4 w-4" /></Button>
          <Button variant="outline" onClick={() => setStart(monday(new Date()))} data-testid="schedule-this-week">This week</Button>
          <Button variant="outline" size="icon" onClick={() => setStart(addDays(start, 7))} data-testid="schedule-next-week"><ChevronRight className="h-4 w-4" /></Button>
        </div>
      </PageHeader>
      <p className="mb-4 font-mono text-xs text-slate-500" data-testid="schedule-range">{fmtDate(iso(days[0]))} – {fmtDate(iso(days[6]))} · {jobs.length} job{jobs.length === 1 ? "" : "s"}</p>
      <div className="grid gap-3 md:grid-cols-7">
        {days.map((d) => {
          const key = iso(d);
          const list = jobs.filter((b) => b.date === key).sort((a, b) => a.slot.localeCompare(b.slot));
          return (
            <div key={key} className={`min-h-32 rounded-2xl border p-2 ${key === today ? "border-teal-500 bg-teal-50/60" : "border-slate-200 bg-slate-50"}`} data-testid={`schedule-day-${key}`}>
              <p className="mb-2 px-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-600">{d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</p>
              <div className="space-y-2">{list.map((b) => <JobCard key={b.id} b={b} color={color(b.assigned_to)} onOpen={setOpen} />)}</div>
              {list.length === 0 && <p className="px-1 text-xs text-slate-400">No jobs</p>}
            </div>
          );
        })}
      </div>
      <BookingDetail b={open} onClose={() => setOpen(null)} />
    </div>
  );
}
