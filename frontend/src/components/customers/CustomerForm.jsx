import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const EMPTY_CUSTOMER = { name: "", phone: "", email: "", address: "", postcode: "", service_interest: "", property_details: "", requirements: "", notes: "", contact_method: "phone", type: "residential", marketing_consent: false };
const METHODS = ["phone", "email", "whatsapp", "walk_in", "referral", "website", "other"];

const F = ({ label: l, children }) => <div className="space-y-1"><Label className="text-xs text-slate-600">{l}</Label>{children}</div>;

export const CustomerForm = ({ v, set, services = [] }) => {
  const bind = (k) => ({ value: v[k] ?? "", onChange: (e) => set({ ...v, [k]: e.target.value }), "data-testid": `customer-${k.replace(/_/g, "-")}-input` });
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="customer-form">
      <F label="Full name *"><Input {...bind("name")} /></F>
      <F label="Phone"><Input type="tel" {...bind("phone")} /></F>
      <F label="Email"><Input type="email" {...bind("email")} /></F>
      <F label="How did they contact us?">
        <Select value={v.contact_method} onValueChange={(x) => set({ ...v, contact_method: x })}>
          <SelectTrigger data-testid="customer-contact-method-select"><SelectValue /></SelectTrigger>
          <SelectContent>{METHODS.map((m) => <SelectItem key={m} value={m} className="capitalize">{m.replace("_", " ")}</SelectItem>)}</SelectContent>
        </Select>
      </F>
      <div className="sm:col-span-2"><F label="Full property address"><Input {...bind("address")} /></F></div>
      <F label="Postcode"><Input {...bind("postcode")} className="uppercase" /></F>
      <F label="Cleaning service required">
        <Select value={v.service_interest || "none"} onValueChange={(x) => set({ ...v, service_interest: x === "none" ? "" : x })}>
          <SelectTrigger data-testid="customer-service-select"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="none">Not decided</SelectItem>{services.map((s) => <SelectItem key={s.key} value={s.key}>{s.name}</SelectItem>)}</SelectContent>
        </Select>
      </F>
      <div className="sm:col-span-2"><F label="Property details (type, bedrooms, bathrooms, size, pets, parking)"><Textarea rows={2} {...bind("property_details")} /></F></div>
      <div className="sm:col-span-2"><F label="Specific cleaning requirements"><Textarea rows={2} {...bind("requirements")} /></F></div>
      <div className="sm:col-span-2"><F label="Special instructions / notes (access, keys, preferences)"><Textarea rows={2} {...bind("notes")} /></F></div>
      <label className="flex items-start gap-2 text-xs text-slate-600 sm:col-span-2">
        <Checkbox checked={v.marketing_consent} onCheckedChange={(x) => set({ ...v, marketing_consent: !!x })} data-testid="customer-marketing-consent-checkbox" />
        Customer agreed to receive marketing messages (record only if they said yes). Booking details are kept to deliver the service we agreed (UK GDPR - contract).
      </label>
    </div>
  );
};
