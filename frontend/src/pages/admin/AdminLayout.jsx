import { Link, NavLink, Outlet } from "react-router-dom";
import { BarChart3, Bot, Building2, CalendarDays, CalendarRange, CreditCard, ExternalLink, LogOut, Mail, Megaphone, ScrollText, Search, Send, Settings, Star, UserCog, Users } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { InstallApp } from "@/components/admin/InstallApp";
import { fmtDate } from "@/lib/api";

const NAV = [
  ["", "Overview", BarChart3, "analytics"], ["leads", "Leads & CRM", Users, "crm"], ["bookings", "Bookings", CalendarDays, "quotes_bookings"], ["schedule", "Staff schedule", CalendarRange, "quotes_bookings"], ["walkthroughs", "Site walkthroughs", Building2, "crm"],
  ["receptionist", "AI receptionist", Bot, "ai_receptionist"], ["growth", "SEO & Google Ads", Search, "marketing"], ["outreach", "Cold email", Send, "outreach"],
  ["reviews", "Reviews", Star, "reviews"], ["marketing", "Marketing spend", Megaphone, "analytics"], ["comms", "Communications", Mail, "crm"],
  ["staff", "Team", UserCog, null], ["policies", "Policies & terms", ScrollText, null], ["settings", "Settings", Settings, null], ["billing", "Billing", CreditCard, null],
];

function Banner({ company }) {
  if (!company.access.ok) return <div className="bg-red-600 px-4 py-2 text-center text-sm text-white" data-testid="access-banner">{company.access.reason}. <Link to="/admin/billing" className="underline">Go to billing</Link></div>;
  if (company.subscription_status === "trialing") return <div className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900" data-testid="trial-banner">Free trial until {fmtDate(company.trial_ends_at)}. <Link to="/admin/billing" className="font-medium underline">Choose a plan</Link></div>;
  if (company.subscription_status === "past_due") return <div className="bg-orange-500 px-4 py-2 text-center text-sm text-white" data-testid="pastdue-banner">Payment failed - update your card within 7 days to keep access. <Link to="/admin/billing" className="underline">Billing</Link></div>;
  return null;
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const c = user.company;
  const allowed = ([to, , , f]) => (user.role === "staff" ? ["bookings", "schedule", "policies"].includes(to) : !f || c.comped || c.features.includes(f));
  const link = ({ isActive }) => `flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-sm transition-colors ${isActive ? "bg-[#8F7E22] text-white" : "text-white/70 hover:bg-white/10 hover:text-white"}`;
  return (
    <div className="min-h-screen bg-[#f6f7f9]" data-testid="admin-layout">
      <Banner company={c} />
      <div className="lg:flex">
        <aside className="bg-[#012b00] lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:flex-col">
          <div className="px-5 py-5">
            <a href="/admin" className="inline-flex rounded-2xl bg-white px-3 py-2" data-testid="admin-logo"><img src="/brand/solidclean-logo.png" alt="Solid Clean Ltd" className="h-10 w-auto" /></a>
            <p className="mt-3 truncate font-display text-base font-bold text-white" data-testid="admin-company-name">{c.slug === "solid-clean" ? "Solid Clean Ltd" : c.name}</p>
            <p className="font-mono text-[10px] uppercase tracking-wider text-[#d9c56a]">Business dashboard</p>
            <a href="/" target="_blank" rel="noreferrer" className="mt-1 flex items-center gap-1 font-mono text-[10px] text-white/60 hover:text-white" data-testid="admin-booking-page-link">View website <ExternalLink className="h-3 w-3" /></a>
            <div className="mt-3"><InstallApp /></div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-y-auto">
            {NAV.filter(allowed).map(([to, t, Icon]) => (
              <NavLink key={t} to={`/admin${to ? `/${to}` : ""}`} end={!to} className={link} data-testid={`admin-nav-${to || "overview"}`}><Icon className="h-4 w-4" />{t}</NavLink>
            ))}
          </nav>
          <div className="hidden border-t border-white/10 p-4 lg:block">
            <p className="truncate font-mono text-xs text-white/50" data-testid="admin-user-email">{user.email} · {user.role}</p>
            <button onClick={logout} className="mt-2 flex items-center gap-2 text-sm text-white/70 hover:text-white" data-testid="admin-logout-btn"><LogOut className="h-4 w-4" />Sign out</button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-8 sm:px-8 lg:px-10"><Outlet /></main>
      </div>
    </div>
  );
}
