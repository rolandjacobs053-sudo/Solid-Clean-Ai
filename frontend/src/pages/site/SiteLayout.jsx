import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Menu, Phone, X } from "lucide-react";
import { ChatWidget } from "@/components/site/ChatWidget";
import { api } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";

export const G = "#023F00";
export const GOLD = "#8F7E22";
const NAV = [["/services", "Services"], ["/areas", "Service areas"], ["/reviews", "Reviews"], ["/faq", "FAQ"], ["/about", "About"], ["/contact", "Contact"]];
const LEGAL = [["/policies", "Company policies"], ["/privacy", "Privacy policy"], ["/cookies", "Cookie policy"], ["/terms", "Terms & conditions"]];

export const BookBtn = ({ children = "Book a Cleaning", className = "", testid = "book-cleaning-btn" }) => (
  <Link to="/quote" data-testid={testid} className={`inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5 ${className}`} style={{ background: G }}>{children}</Link>
);

function Header({ b }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const link = ({ isActive }) => `text-sm font-medium transition-colors hover:text-[#8F7E22] ${isActive ? "text-[#8F7E22]" : "text-slate-700"}`;
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur-xl" data-testid="site-header">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" data-testid="site-logo"><img src={b.logo_url || "/brand/solidclean-logo.png"} alt={b.name} className="h-14 w-auto" /></Link>
        <nav className="hidden items-center gap-6 lg:flex">{NAV.map(([to, t]) => <NavLink key={to} to={to} className={link} data-testid={`site-nav-${to.slice(1)}`}>{t}</NavLink>)}</nav>
        <div className="hidden items-center gap-3 md:flex">
          {b.phone && <a href={`tel:${b.phone.replace(/\s/g, "")}`} className="flex items-center gap-1.5 font-mono text-sm font-semibold" style={{ color: G }} data-testid="site-phone"><Phone className="h-4 w-4" />{b.phone}</a>}
          <BookBtn className="!px-5 !py-2.5" testid="header-book-btn" />
        </div>
        <button className="lg:hidden" onClick={() => setOpen(!open)} data-testid="site-menu-btn">{open ? <X /> : <Menu />}</button>
      </div>
      {open && (
        <nav className="space-y-1 border-t bg-white px-4 py-4 lg:hidden" data-testid="site-mobile-nav">
          {NAV.map(([to, t]) => <NavLink key={to} to={to} className="block rounded-lg px-3 py-2 text-slate-700 hover:bg-slate-50">{t}</NavLink>)}
          <div className="flex gap-2 pt-2"><BookBtn className="flex-1" testid="mobile-book-btn" /></div>
        </nav>
      )}
    </header>
  );
}

function Footer({ b }) {
  return (
    <footer className="mt-20 text-white/80" style={{ background: G }} data-testid="site-footer">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4 lg:px-8">
        <div className="md:col-span-2">
          <p className="font-display text-xl font-bold text-white">{b.name}</p>
          <p className="mt-3 max-w-sm text-sm">Residential, End of Tenancy, carpet and commercial cleaning{b.service_areas_text ? ` across ${b.service_areas_text}` : ""}.</p>
          {b.phone && <a href={`tel:${b.phone.replace(/\s/g, "")}`} className="mt-4 block font-mono text-lg font-semibold" style={{ color: "#d9c56a" }}>{b.phone}</a>}
        </div>
        <div className="space-y-2 text-sm">{NAV.map(([to, t]) => <Link key={to} to={to} className="block hover:text-white">{t}</Link>)}</div>
        <div className="space-y-2 text-sm">{LEGAL.map(([to, t]) => <Link key={to} to={to} className="block hover:text-white" data-testid={`footer-${to.slice(1)}`}>{t}</Link>)}<Link to="/unsubscribe" className="block hover:text-white">Marketing preferences</Link></div>
      </div>
      <div className="border-t border-white/10 py-5 text-center font-mono text-xs">© {new Date().getFullYear()} {b.name}</div>
    </footer>
  );
}

export default function SiteLayout() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get(`/public/${DEFAULT_SLUG}/config`).then((r) => setCfg(r.data)).catch(() => {}); }, []);
  if (!cfg) return <div className="p-16 text-center font-mono text-sm text-slate-400">Loading…</div>;
  return (
    <div className="brand-site" data-testid="public-site">
      <Header b={cfg.business} />
      <Outlet context={cfg} />
      <Footer b={cfg.business} />
      {cfg.ai_receptionist && <ChatWidget />}
    </div>
  );
}
