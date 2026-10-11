import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

export const Logo = ({ dark = false, name = "CleanOps", to = "/" }) => (
  <Link to={to} className="flex items-center gap-2" data-testid="site-logo-link">
    <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-600 text-white"><Sparkles className="h-4 w-4" /></span>
    <span className={`font-display text-lg font-bold tracking-tight ${dark ? "text-white" : "text-slate-900"}`}>{name}<span className="text-teal-500">.</span></span>
  </Link>
);

export function BookingHeader({ name, base }) {
  return (
    <header className="border-b border-slate-200/70 bg-white/70 backdrop-blur-xl" data-testid="booking-header">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo name={name || "…"} to={`${base}/quote`} />
        <span className="font-mono text-[10px] uppercase tracking-widest text-slate-400">Online booking · powered by CleanOps</span>
      </div>
    </header>
  );
}
