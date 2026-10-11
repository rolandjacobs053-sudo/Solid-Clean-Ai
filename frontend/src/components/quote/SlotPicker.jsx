import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import { api } from "@/lib/api";
import { useTenant } from "@/lib/tenant";

export function SlotPicker({ availability, date, setDate, slot, setSlot }) {
  const { pub } = useTenant();
  const [slots, setSlots] = useState(null);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const first = new Date(today.getTime() + availability.min_notice_days * 86400000);
  const last = new Date(today.getTime() + availability.max_advance_days * 86400000);
  const disabled = (d) =>
    d < first || d > last || !availability.working_days.includes((d.getDay() + 6) % 7) || availability.blocked_dates.includes(format(d, "yyyy-MM-dd"));

  useEffect(() => {
    if (!date) return;
    setSlots(null);
    api.get(`${pub}/availability`, { params: { date: format(date, "yyyy-MM-dd") } }).then((r) => setSlots(r.data.slots));
  }, [date, pub]);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-2" data-testid="quote-calendar">
        <Calendar mode="single" selected={date} onSelect={(d) => { setDate(d); setSlot(""); }} disabled={disabled} fromDate={first} toDate={last} />
      </div>
      <div>
        <p className="eyebrow">Available times</p>
        {!date && <p className="mt-3 text-sm text-slate-500">Pick a date to see live availability.</p>}
        {date && slots === null && <p className="mt-3 text-sm text-slate-500">Checking availability…</p>}
        {slots?.length === 0 && <p className="mt-3 text-sm text-amber-700" data-testid="quote-no-slots">Fully booked - please choose another date.</p>}
        <div className="mt-3 grid grid-cols-2 gap-3">
          {slots?.map((s) => (
            <button key={s.slot} type="button" onClick={() => setSlot(s.slot)} data-testid={`quote-slot-${s.slot.replace(":", "")}`}
              className={`rounded-2xl border px-4 py-3 text-left transition-colors ${slot === s.slot ? "border-teal-600 bg-teal-50 ring-1 ring-teal-600" : "border-slate-200 bg-white hover:border-teal-300"}`}>
              <p className="font-mono text-lg font-semibold text-slate-900">{s.slot}</p>
              <p className="text-xs text-slate-500">{s.remaining} team{s.remaining > 1 ? "s" : ""} free</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
