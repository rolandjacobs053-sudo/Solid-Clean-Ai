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
import TipPage from "@/pages/site/TipPage";
import ResultsPage from "@/pages/site/ResultsPage";
import ResidentialBooking from "@/pages/site/ResidentialBooking";
import FeedbackPage from "@/pages/site/FeedbackPage";
import Unsubscribe from "@/pages/Unsubscribe";
import AdminLogin from "@/pages/AdminLogin";
import Signup from "@/pages/Signup";
import AdminLayout from "@/pages/admin/AdminLayout";
import Overview from "@/pages/admin/Overview";
import Leads from "@/pages/admin/Leads";
import Bookings from "@/pages/admin/Bookings";
import Schedule from "@/pages/admin/Schedule";
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
import SiteLayout from "@/pages/site/SiteLayout";
import CommercialPage from "@/pages/site/CommercialPage";
import CommercialRequest from "@/pages/site/CommercialRequest";
import Walkthroughs from "@/pages/admin/Walkthroughs";
import CarpetQuotes from "@/pages/admin/CarpetQuotes";
import RegularClients from "@/pages/admin/RegularClients";
import CarpetPage from "@/pages/site/CarpetPage";
import CarpetRequest from "@/pages/site/CarpetRequest";
import CarpetQuoteView from "@/pages/site/CarpetQuoteView";
import { AboutPage, AreasPage, ContactPage, FaqPage, HomePage, PolicyPage, ReviewsPage, ServiceDetail, ServicesPage } from "@/pages/site/SitePages";
import Policies from "@/pages/admin/Policies";
import PublicPolicies from "@/pages/PublicPolicies";

function BookingLayout() {
  const { slug, base, pub } = useTenant();
  const [cfg, setCfg] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`${pub}/config`).then((r) => setCfg(r.data)).catch((e) => setError(e?.response?.data?.detail || "Booking page not found")); }, [pub]);
  if (error) return <div className="p-16 text-center text-slate-600" data-testid="booking-unavailable">{error}</div>;
  return (
    <>
      <BookingHeader cfg={cfg} base={base} />
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
  if (!user) return <Navigate to="/admin/login" replace />;
  if (user.role === "platform_admin") return <Navigate to="/platform" replace />;
  if (user.role === "staff" && !/^\/admin\/(bookings|schedule|policies)/.test(loc.pathname)) return <Navigate to="/admin/bookings" replace />;
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
            <Route element={<SiteLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/services" element={<ServicesPage />} />
              <Route path="/services/commercial" element={<Navigate to="/commercial-cleaning" replace />} />
              <Route path="/commercial-cleaning" element={<CommercialPage />} />
              <Route path="/commercial-cleaning/request" element={<CommercialRequest />} />
              <Route path="/services/carpet" element={<Navigate to="/carpet-cleaning" replace />} />
              <Route path="/carpet-cleaning" element={<CarpetPage />} />
              <Route path="/residential-cleaning/book" element={<ResidentialBooking />} />
              <Route path="/carpet-cleaning/request" element={<CarpetRequest />} />
              <Route path="/carpet-cleaning/quote/:id" element={<CarpetQuoteView />} />
              <Route path="/services/:key" element={<ServiceDetail />} />
              <Route path="/quote" element={<QuotePage />} />
              <Route path="/book" element={<Navigate to="/quote" replace />} />
              <Route path="/payment/:result" element={<PaymentResult />} />
              <Route path="/tip/:bookingId" element={<TipPage />} />
              <Route path="/results/:bookingId" element={<ResultsPage />} />
              <Route path="/feedback/:bookingId" element={<FeedbackPage />} />
              <Route path="/unsubscribe" element={<Unsubscribe />} />
              <Route path="/faq" element={<FaqPage />} />
              <Route path="/areas" element={<AreasPage />} />
              <Route path="/reviews" element={<ReviewsPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/contact" element={<ContactPage />} />
              <Route path="/policies" element={<PublicPolicies />} />
              <Route path="/privacy" element={<PolicyPage policyKey="privacy" />} />
              <Route path="/cookies" element={<PolicyPage policyKey="cookies" />} />
              <Route path="/terms" element={<PolicyPage policyKey="terms" />} />
            </Route>
            <Route path="/login" element={<AdminLogin />} />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/app" element={<Root />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/c/:slug" element={<BookingLayout />}>
              <Route index element={<Navigate to="quote" replace />} />
              <Route path="quote" element={<QuotePage />} />
              <Route path="payment/:result" element={<PaymentResult />} />
              <Route path="unsubscribe" element={<Unsubscribe />} />
              <Route path="policies" element={<PublicPolicies />} />
            </Route>
            <Route path="/admin" element={<CompanyArea />}>
              <Route index element={<Overview />} />
              <Route path="leads" element={<Leads />} />
              <Route path="bookings" element={<Bookings />} />
              <Route path="schedule" element={<Schedule />} />
              <Route path="walkthroughs" element={<Walkthroughs />} />
              <Route path="carpet-quotes" element={<CarpetQuotes />} />
              <Route path="regular-clients" element={<RegularClients />} />
              <Route path="receptionist" element={<Conversations />} />
              <Route path="outreach" element={<Outreach />} />
              <Route path="reviews" element={<Reviews />} />
              <Route path="growth" element={<GrowthTools />} />
              <Route path="marketing" element={<Marketing />} />
              <Route path="comms" element={<Comms />} />
              <Route path="staff" element={<Staff />} />
              <Route path="settings" element={<Settings />} />
              <Route path="policies" element={<Policies />} />
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
