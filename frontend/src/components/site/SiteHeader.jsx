import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

export const Logo = ({ dark = false, name = "CleanOps", to = "/" }) => (
  <Link to={to} className="flex items-center gap-2" data-testid="site-logo-link">
    <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-600 text-white"><Sparkles className="h-4 w-4" /></span>
    <span className={`font-display text-lg font-bold tracking-tight ${dark ? "text-white" : "text-slate-900"}`}>{name}<span className="text-teal-500">.</span></span>
  </Link>
);

export function BookingHeader({ cfg, base }) {
  const b = cfg?.business || {};
  return (
    <header className="border-b border-slate-200/70 bg-white/80 backdrop-blur-xl" style={{ borderTop: `4px solid ${b.brand_primary || "#0F766E"}` }} data-testid="booking-header">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        {b.logo_url
          ? <Link to={`${base}/quote`} data-testid="booking-logo"><img src={b.logo_url} alt={b.name} className="h-11 w-auto" /></Link>
          : <Logo name={b.name || "…"} to={`${base}/quote`} />}
        <div className="flex items-center gap-4 text-sm">
          <Link to={`${base}/policies`} className="text-slate-600 hover:underline" data-testid="booking-policies-link">Policies</Link>
          {b.phone && !b.phone.startsWith("[") && <a href={`tel:${b.phone.replace(/\s/g, "")}`} className="font-mono font-semibold" style={{ color: b.brand_primary }} data-testid="booking-phone">{b.phone}</a>}
        </div>
      </div>
    </header>
  );
}
