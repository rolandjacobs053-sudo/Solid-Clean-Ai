import { useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errMsg } from "@/lib/api";
import { useTenant } from "@/lib/tenant";

export default function Unsubscribe() {
  const cfg = useOutletContext();
  const { pub } = useTenant();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") || "");
  const [done, setDone] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post(`${pub}/optout`, { email }); setDone(true); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <main className="mx-auto max-w-md px-4 py-24" data-testid="unsubscribe-page">
      <p className="eyebrow">Marketing preferences</p>
      <h1 className="mt-3 text-3xl font-bold text-slate-900">Unsubscribe</h1>
      {done ? (
        <p className="mt-6 text-slate-600" data-testid="unsubscribe-success">Done - {email} will not receive any further marketing from {cfg?.business.name || "this company"}. Service messages about existing bookings may still be sent.</p>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-3">
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" data-testid="unsubscribe-email-input" />
          <Button className="w-full rounded-full bg-slate-900 hover:bg-teal-700 hover:text-white" data-testid="unsubscribe-submit-btn">Stop marketing emails</Button>
        </form>
      )}
    </main>
  );
}
