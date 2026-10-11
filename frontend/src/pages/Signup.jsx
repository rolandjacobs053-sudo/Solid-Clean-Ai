import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";
import { Logo } from "@/components/site/SiteHeader";

const FIELDS = [["company_name", "Company name", "text"], ["name", "Your name", "text"], ["email", "Work email", "email"], ["password", "Password (8+ characters)", "password"], ["country", "Country", "text"]];

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [f, setF] = useState({ company_name: "", name: "", email: "", password: "", country: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await signup(f); navigate("/admin/settings"); } catch (err) { setError(errMsg(err)); }
    setBusy(false);
  };
  return (
    <main className="grid min-h-screen lg:grid-cols-2" data-testid="signup-page">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-slate-950 p-12 text-white lg:flex grain">
        <Logo dark />
        <div>
          <p className="eyebrow !text-teal-400">14-day free trial · no card needed</p>
          <h1 className="mt-4 max-w-md text-5xl font-extrabold leading-tight tracking-tight">Run and grow your cleaning business from one dashboard.</h1>
          <ul className="mt-8 space-y-2 text-sm text-slate-300">
            {["Instant quotes from your own price list", "Online bookings with live availability & Stripe payments", "AI receptionist, CRM, reviews and outreach", "Analytics: cost per lead, CAC and profit by channel"].map((t) => <li key={t}>— {t}</li>)}
          </ul>
        </div>
        <p className="font-mono text-xs text-slate-500">Each company gets its own private workspace and data.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4">
          <div className="lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-bold text-slate-900">Create your company account</h2>
          {FIELDS.map(([k, l, t]) => (
            <div key={k}><Label htmlFor={k}>{l}</Label>
              <Input id={k} type={t} required={k !== "country"} minLength={k === "password" ? 8 : undefined} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="mt-1.5 h-11" data-testid={`signup-${k}-input`} />
            </div>
          ))}
          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="signup-error">{error}</p>}
          <Button disabled={busy} className="h-11 w-full rounded-full bg-teal-600 hover:bg-teal-700" data-testid="signup-submit-btn">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Start free trial</Button>
          <p className="text-center text-sm text-slate-500">Already have an account? <Link to="/login" className="font-medium text-teal-700 hover:underline" data-testid="signup-login-link">Sign in</Link></p>
        </form>
      </div>
    </main>
  );
}
