import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { homeFor, useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";

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
      <div className="relative hidden overflow-hidden bg-[#023F00] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <span className="inline-flex w-fit rounded-2xl bg-white px-4 py-3"><img src="/brand/solidclean-logo.png" alt="Solid Clean Ltd" className="h-14 w-auto" /></span>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#d9c56a]">Business dashboard</p>
          <h1 className="mt-4 max-w-md text-5xl font-extrabold leading-tight tracking-tight">Solid Clean Ltd</h1>
        </div>
        <p className="font-mono text-xs text-white/60">Bookings, customers, staff schedule, site walkthroughs and enquiries - one secure login.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5">
          <div className="lg:hidden"><img src="/brand/solidclean-logo.png" alt="Solid Clean Ltd" className="h-14 w-auto" /></div>
          <h2 className="text-2xl font-bold text-slate-900">Sign in to Solid Clean Ltd</h2>
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 h-11" data-testid="admin-login-email-input" /></div>
          <div><Label htmlFor="pw">Password</Label><Input id="pw" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 h-11" data-testid="admin-login-password-input" /></div>
          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="admin-login-error">{error}</p>}
          <Button disabled={busy} className="h-11 w-full rounded-full bg-[#023F00] text-white hover:bg-[#8F7E22]" data-testid="admin-login-submit-btn">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Sign in
          </Button>
          {open && <p className="text-center text-sm text-slate-500">New cleaning company? <Link to="/signup" className="font-medium text-[#023F00] hover:underline" data-testid="login-signup-link">Start a 14-day free trial</Link></p>}
        </form>
      </div>
    </main>
  );
}
