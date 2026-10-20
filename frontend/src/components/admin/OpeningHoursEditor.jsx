import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { defaultHours, hoursText } from "@/lib/hours";

export const OpeningHoursEditor = ({ value, onChange }) => {
  if (!value) {
    return <Button variant="outline" onClick={() => onChange(defaultHours())} data-testid="opening-hours-setup-btn">Set opening hours</Button>;
  }
  const edit = (i, k, v) => onChange(value.map((d, j) => (j === i ? { ...d, [k]: v } : d)));
  return (
    <div className="space-y-2" data-testid="opening-hours-editor">
      {value.map((d, i) => (
        <div key={d.day} className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 px-3 py-2">
          <span className="w-24 text-sm font-medium">{d.day}</span>
          <Switch checked={d.open} onCheckedChange={(v) => edit(i, "open", v)} data-testid={`opening-hours-${d.day.toLowerCase()}-open`} />
          {d.open ? (
            <>
              <Input type="time" value={d.from} onChange={(e) => edit(i, "from", e.target.value)} className="w-32 font-mono" data-testid={`opening-hours-${d.day.toLowerCase()}-from`} />
              <span className="text-slate-400">to</span>
              <Input type="time" value={d.to} onChange={(e) => edit(i, "to", e.target.value)} className="w-32 font-mono" data-testid={`opening-hours-${d.day.toLowerCase()}-to`} />
            </>
          ) : <span className="text-sm text-slate-400">Closed</span>}
        </div>
      ))}
      <Label className="block pt-2 text-xs text-slate-500" data-testid="opening-hours-preview">Shown on website and Google: {hoursText(value) || "nothing yet - switch on the days you are open"}</Label>
    </div>
  );
};
