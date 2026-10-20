import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Copy, Menu, Phone, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ChatWidget } from "@/components/site/ChatWidget";
import { api } from "@/lib/api";
import { DEFAULT_SLUG } from "@/lib/tenant";
import { hoursSchema } from "@/lib/hours";

export const G = "#023F00";
export const GOLD = "#8F7E22";
const NAV = [["/services", "Services"], ["/carpet-cleaning", "Carpet"], ["/commercial-cleaning", "Commercial"], ["/areas", "Service areas"], ["/reviews", "Reviews"], ["/faq", "FAQ"], ["/about", "About"], ["/contact", "Contact"]];
const LEGAL = [["/policies", "Company policies"], ["/privacy", "Privacy policy"], ["/cookies", "Cookie policy"], ["/terms", "Terms & conditions"]];

export const BookBtn = ({ children = "Book a Cleaning", className = "", testid = "book-cleaning-btn" }) => (
  <Link to="/quote" data-testid={testid} className={`inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5 ${className}`} style={{ background: G }}>{children}</Link>
);
export const tel = (phone) => { const d = (phone || "").replace(/[^\d+]/g, ""); return `tel:${d.startsWith("0") ? `+44${d.slice(1)}` : d}`; };

export function CallDialog({ phone }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onClick = (e) => {
      const a = e.target.closest?.('a[href^="tel:"]');
      if (!a || a.dataset.direct || window.matchMedia("(pointer: coarse)").matches) return;
      e.preventDefault();
      setOpen(true);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  const copy = async () => { try { await navigator.clipboard.writeText(phone); toast.success("Number copied"); } catch { toast.error(`Please dial ${phone}`); } };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-sm text-center" data-testid="call-dialog">
        <DialogHeader><DialogTitle className="text-center">Call Solid Clean Ltd</DialogTitle><DialogDescription className="text-center">Speak to our team on</DialogDescription></DialogHeader>
        <p className="font-mono text-3xl font-bold" style={{ color: G }} data-testid="call-dialog-number">{phone}</p>
        <div className="mt-2 flex flex-col gap-2">
          <button type="button" onClick={copy} className="flex items-center justify-center gap-2 rounded-full py-3 text-sm font-semibold text-white" style={{ background: G }} data-testid="call-dialog-copy-btn"><Copy className="h-4 w-4" />Copy number</button>
          <a href={tel(phone)} data-direct="1" className="rounded-full border-2 py-3 text-sm font-semibold" style={{ borderColor: GOLD, color: G }} data-testid="call-dialog-call-btn">Call with a calling app</a>
        </div>
      </DialogContent>
    </Dialog>
  );
}
export const CallBtn = ({ phone, className = "", testid = "call-btn", label }) => (
  <a href={tel(phone)} data-testid={testid} className={`inline-flex items-center justify-center gap-2 rounded-full border-2 px-6 py-3 text-sm font-semibold transition-colors hover:bg-[#8F7E22]/10 ${className}`} style={{ borderColor: GOLD, color: G }}><Phone className="h-4 w-4" />{label || `Call ${phone}`}</a>
);

function CallStrip({ b }) {
  return (
    <div className="text-white" style={{ background: G }} data-testid="site-call-strip">
      <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 px-4 py-2 text-xs sm:justify-between sm:text-sm lg:px-8">
        <span className="hidden sm:inline">Professional cleaning{b.service_areas_text ? ` across ${b.service_areas_text}` : ""} · Fully insured</span>
        <a href={tel(b.phone)} className="flex items-center gap-2 font-semibold" data-testid="call-strip-phone"><Phone className="h-3.5 w-3.5" style={{ color: "#d9c56a" }} />Speak to our team: <span className="font-mono">{b.phone}</span></a>
      </div>
    </div>
  );
}

function MobileCallBar({ b }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-2 gap-2 border-t border-slate-200 bg-white/95 p-3 backdrop-blur-xl md:hidden" data-testid="mobile-call-bar">
      <a href={tel(b.phone)} className="flex items-center justify-center gap-2 rounded-full py-3 text-sm font-semibold text-white" style={{ background: GOLD }} data-testid="mobile-call-btn"><Phone className="h-4 w-4" />Call us</a>
      <BookBtn className="!py-3" testid="mobile-bar-book-btn">Book online</BookBtn>
    </div>
  );
}

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
          {b.phone && <a href={tel(b.phone)} className="flex items-center gap-2 rounded-full border-2 px-4 py-2 font-mono text-sm font-semibold transition-colors hover:bg-[#8F7E22]/10" style={{ color: G, borderColor: GOLD }} data-testid="site-phone"><Phone className="h-4 w-4" />{b.phone}</a>}
          <BookBtn className="!px-5 !py-2.5" testid="header-book-btn" />
        </div>
        <div className="flex items-center gap-3 lg:hidden">
          {b.phone && <a href={tel(b.phone)} className="rounded-full p-2.5 text-white md:hidden" style={{ background: GOLD }} aria-label="Call us" data-testid="header-call-icon"><Phone className="h-4 w-4" /></a>}
          <button onClick={() => setOpen(!open)} data-testid="site-menu-btn">{open ? <X /> : <Menu />}</button>
        </div>
      </div>
      {open && (
        <nav className="space-y-1 border-t bg-white px-4 py-4 lg:hidden" data-testid="site-mobile-nav">
          {NAV.map(([to, t]) => <NavLink key={to} to={to} className="block rounded-lg px-3 py-2 text-slate-700 hover:bg-slate-50">{t}</NavLink>)}
          <div className="flex gap-2 pt-2"><BookBtn className="flex-1" testid="mobile-book-btn" />{b.phone && <CallBtn phone={b.phone} className="flex-1" testid="mobile-menu-call-btn" label="Call us" />}</div>
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
          {b.phone && <a href={tel(b.phone)} className="mt-4 block font-mono text-lg font-semibold" style={{ color: "#d9c56a" }}>{b.phone}</a>}
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
  const loc = useLocation();
  useEffect(() => { api.get(`/public/${DEFAULT_SLUG}/config`).then((r) => setCfg(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    const el = document.head.querySelector('script[type="application/ld+json"]');
    const spec = hoursSchema(cfg?.business.opening_hours);
    if (!el || !spec.length) return;
    el.textContent = JSON.stringify({ ...JSON.parse(el.textContent), openingHoursSpecification: spec });
  }, [cfg]);
  if (!cfg) return <div className="p-16 text-center font-mono text-sm text-slate-400">Loading…</div>;
  return (
    <div className="brand-site pb-20 md:pb-0" data-testid="public-site">
      {cfg.business.phone && <CallStrip b={cfg.business} />}
      <Header b={cfg.business} />
      <Outlet context={cfg} />
      <Footer b={cfg.business} />
      {cfg.business.phone && !loc.pathname.startsWith("/quote") && !loc.pathname.startsWith("/commercial-cleaning/request") && !loc.pathname.startsWith("/carpet-cleaning/request") && !loc.pathname.startsWith("/residential-cleaning") && !loc.pathname.startsWith("/feedback") && <MobileCallBar b={cfg.business} />}
      {cfg.business.phone && <CallDialog phone={cfg.business.phone} />}
      {cfg.ai_receptionist && <ChatWidget />}
    </div>
  );
}
