import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, Building2, CreditCard, FileSpreadsheet, FileText, Layers, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/site/SiteHeader";

const NAV = [["", "Overview", BarChart3], ["companies", "Companies", Building2], ["plans", "Plans", Layers], ["payments", "Payments", CreditCard],
  ["quotation", "Quotation", FileSpreadsheet], ["proposal", "Solid Clean proposal", FileText]];

export default function PlatformLayout() {
  const { user, logout } = useAuth();
  const link = ({ isActive }) => `flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-sm transition-colors ${isActive ? "bg-amber-500 text-slate-950" : "text-slate-400 hover:bg-slate-800 hover:text-white"}`;
  return (
    <div className="min-h-screen bg-[#f6f7f9] lg:flex" data-testid="platform-layout">
      <aside className="bg-slate-950 lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:flex-col">
        <div className="px-5 py-5"><Logo dark to="/platform" /><p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-amber-400">Platform admin</p></div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col">
          {NAV.map(([to, t, Icon]) => <NavLink key={t} to={`/platform${to ? `/${to}` : ""}`} end={!to} className={link} data-testid={`platform-nav-${to || "overview"}`}><Icon className="h-4 w-4" />{t}</NavLink>)}
        </nav>
        <div className="border-t border-slate-800 p-4">
          <p className="truncate font-mono text-xs text-slate-500">{user?.email}</p>
          <button onClick={logout} className="mt-2 flex items-center gap-2 text-sm text-slate-400 hover:text-white" data-testid="platform-logout-btn"><LogOut className="h-4 w-4" />Sign out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-8 sm:px-8 lg:px-10"><Outlet /></main>
    </div>
  );
}
