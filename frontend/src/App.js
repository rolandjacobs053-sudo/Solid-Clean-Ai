import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, homeFor, useAuth } from "@/context/AuthContext";
import { api, getSource } from "@/lib/api";
import { useTenant } from "@/lib/tenant";
import { BookingHeader } from "@/components/site/SiteHeader";
import { ChatWidget } from "@/components/site/ChatWidget";
import QuotePage from "@/pages/QuotePage";
import PaymentResult from "@/pages/PaymentResult";
import Unsubscribe from "@/pages/Unsubscribe";
import AdminLogin from "@/pages/AdminLogin";
import Signup from "@/pages/Signup";
import AdminLayout from "@/pages/admin/AdminLayout";
import Overview from "@/pages/admin/Overview";
import Leads from "@/pages/admin/Leads";
import Bookings from "@/pages/admin/Bookings";
import Conversations from "@/pages/admin/Conversations";
import Outreach from "@/pages/admin/Outreach";
import Reviews from "@/pages/admin/Reviews";
import Marketing from "@/pages/admin/Marketing";
import GrowthTools from "@/pages/admin/GrowthTools";
import Comms from "@/pages/admin/Comms";
import Settings from "@/pages/admin/Settings";
import Staff from "@/pages/admin/Staff";
import Billing from "@/pages/admin/Billing";
import PlatformLayout from "@/pages/platform/PlatformLayout";
import PlatformOverview from "@/pages/platform/PlatformOverview";
import Companies from "@/pages/platform/Companies";
import Plans from "@/pages/platform/Plans";
import Payments from "@/pages/platform/Payments";
import Quotation from "@/pages/platform/Quotation";
import Proposal from "@/pages/admin/Proposal";

function BookingLayout() {
  const { slug, base, pub } = useTenant();
  const [cfg, setCfg] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`${pub}/config`).then((r) => setCfg(r.data)).catch((e) => setError(e?.response?.data?.detail || "Booking page not found")); }, [pub]);
  if (error) return <div className="p-16 text-center text-slate-600" data-testid="booking-unavailable">{error}</div>;
  return (
    <>
      <BookingHeader name={cfg?.business.name} base={base} />
      <Outlet context={cfg} />
      {cfg?.ai_receptionist && <ChatWidget key={slug} />}
    </>
  );
}

const Loading = () => <div className="p-10 font-mono text-sm text-slate-500" data-testid="auth-loading">Checking session…</div>;

const Root = () => {
  const { user } = useAuth();
  if (user === null) return <Loading />;
  return <Navigate to={user ? homeFor(user) : "/login"} replace />;
};

const CompanyArea = () => {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "platform_admin") return <Navigate to="/platform" replace />;
  if (!user.company.access.ok && loc.pathname !== "/admin/billing") return <Navigate to="/admin/billing" replace />;
  return <AdminLayout />;
};

const PlatformArea = () => {
  const { user } = useAuth();
  if (user === null) return <Loading />;
  return user?.role === "platform_admin" ? <PlatformLayout /> : <Navigate to="/login" replace />;
};

function App() {
  useEffect(() => { getSource(); }, []);
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Root />} />
            <Route path="/login" element={<AdminLogin />} />
            <Route path="/admin/login" element={<Navigate to="/login" replace />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/c/:slug" element={<BookingLayout />}>
              <Route index element={<Navigate to="quote" replace />} />
              <Route path="quote" element={<QuotePage />} />
              <Route path="payment/:result" element={<PaymentResult />} />
              <Route path="unsubscribe" element={<Unsubscribe />} />
            </Route>
            <Route path="/admin" element={<CompanyArea />}>
              <Route index element={<Overview />} />
              <Route path="leads" element={<Leads />} />
              <Route path="bookings" element={<Bookings />} />
              <Route path="receptionist" element={<Conversations />} />
              <Route path="outreach" element={<Outreach />} />
              <Route path="reviews" element={<Reviews />} />
              <Route path="growth" element={<GrowthTools />} />
              <Route path="marketing" element={<Marketing />} />
              <Route path="comms" element={<Comms />} />
              <Route path="staff" element={<Staff />} />
              <Route path="settings" element={<Settings />} />
              <Route path="billing" element={<Billing />} />
            </Route>
            <Route path="/platform" element={<PlatformArea />}>
              <Route index element={<PlatformOverview />} />
              <Route path="companies" element={<Companies />} />
              <Route path="plans" element={<Plans />} />
              <Route path="payments" element={<Payments />} />
              <Route path="quotation" element={<Quotation />} />
              <Route path="proposal" element={<Proposal />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
