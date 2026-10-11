import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { homeFor, useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { Logo } from "@/components/site/SiteHeader";

export default function AdminLogin() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => { api.get("/saas/status").then((r) => setOpen(r.data.signup_enabled)).catch(() => {}); }, []);
  if (user) return <Navigate to={homeFor(user)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { const u = await login(email, password); navigate(homeFor(u)); } catch (err) { setError(errMsg(err)); }
    setBusy(false);
  };

  return (
    <main className="grid min-h-screen lg:grid-cols-2" data-testid="admin-login-page">
      <div className="relative hidden overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:flex-col lg:justify-between grain">
        <Logo dark />
        <div>
          <p className="eyebrow !text-teal-400">Command centre</p>
          <h1 className="mt-4 max-w-md text-5xl font-extrabold leading-tight tracking-tight">The AI operating system for cleaning companies.</h1>
        </div>
        <p className="font-mono text-xs text-slate-500">Quotes, bookings, CRM, AI receptionist, outreach and analytics - one login.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5">
          <div className="lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-bold text-slate-900">Sign in</h2>
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 h-11" data-testid="admin-login-email-input" /></div>
          <div><Label htmlFor="pw">Password</Label><Input id="pw" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 h-11" data-testid="admin-login-password-input" /></div>
          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="admin-login-error">{error}</p>}
          <Button disabled={busy} className="h-11 w-full rounded-full bg-slate-900 hover:bg-teal-700 hover:text-white" data-testid="admin-login-submit-btn">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Sign in
          </Button>
          {open && <p className="text-center text-sm text-slate-500">New cleaning company? <Link to="/signup" className="font-medium text-teal-700 hover:underline" data-testid="login-signup-link">Start a 14-day free trial</Link></p>}
        </form>
      </div>
    </main>
  );
}
