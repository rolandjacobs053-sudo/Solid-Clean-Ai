import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const SITE = "https://solidcleanltd.com";
const BRAND = "Solid Clean Ltd";
const DEFAULT = ["Professional Cleaning in London & Surrey", "Solid Clean Ltd - professional residential, end of tenancy, carpet and commercial cleaning across London and Surrey. Book online or call 020 3728 4419."];
const PAGES = {
  "/": DEFAULT,
  "/services": ["Cleaning Services in London & Surrey", "Residential, end of tenancy, carpet and commercial cleaning from Solid Clean Ltd. Instant online prices and booking across London and Surrey."],
  "/services/regular": ["Residential & Regular House Cleaning", "Weekly, fortnightly, monthly or one-off home cleaning across London and Surrey. Get an instant price and book online with Solid Clean Ltd."],
  "/services/end_of_tenancy": ["End of Tenancy Cleaning London & Surrey", "Thorough move-out cleaning for tenants, landlords and letting agents. Instant online price and booking with Solid Clean Ltd."],
  "/carpet-cleaning": ["Carpet Cleaning London & Surrey", "Professional carpet and rug cleaning for homes and workplaces. Send photos for a free quote from Solid Clean Ltd."],
  "/carpet-cleaning/request": ["Request a Carpet Cleaning Quote", "Tell us about your carpets and upload photos to get a carpet cleaning quote from Solid Clean Ltd."],
  "/commercial-cleaning": ["Commercial & Office Cleaning London & Surrey", "Office, workplace and commercial cleaning across London and Surrey. Book a free walkthrough with Solid Clean Ltd."],
  "/commercial-cleaning/request": ["Book a Commercial Cleaning Walkthrough", "Request a free site walkthrough and tailored commercial cleaning quote from Solid Clean Ltd."],
  "/residential-cleaning/book": ["Book a Home Cleaning Online", "Get an instant home cleaning price and book a one-off or regular clean online with Solid Clean Ltd."],
  "/quote": ["Get an Instant Cleaning Quote", "Get an instant cleaning price and book online in minutes with Solid Clean Ltd, London and Surrey."],
  "/areas": ["Areas We Cover - London & Surrey", "Solid Clean Ltd provides professional cleaning services across London and Surrey. Check the areas we cover."],
  "/reviews": ["Customer Reviews", "Read genuine reviews from Solid Clean Ltd customers across London and Surrey."],
  "/faq": ["Cleaning FAQs", "Answers to common questions about Solid Clean Ltd cleaning services, booking, payment and cancellations."],
  "/about": ["About Us", "About Solid Clean Ltd - a professional, fully insured cleaning company serving London and Surrey."],
  "/contact": ["Contact Us", "Contact Solid Clean Ltd on 020 3728 4419 or info@solidcleanltd.com for cleaning in London and Surrey."],
  "/policies": ["Company Policies", "Solid Clean Ltd company policies."],
  "/privacy": ["Privacy Policy", "How Solid Clean Ltd collects and uses your personal data."],
  "/cookies": ["Cookie Policy", "How Solid Clean Ltd uses cookies on this website."],
  "/terms": ["Terms & Conditions", "Solid Clean Ltd terms and conditions of service."],
};

const setMeta = (attr, key, content) => {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) { el = document.createElement("meta"); el.setAttribute(attr, key); document.head.appendChild(el); }
  el.setAttribute("content", content);
};
const setCanonical = (href) => {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) { el = document.createElement("link"); el.rel = "canonical"; document.head.appendChild(el); }
  el.href = href;
};

export const SeoManager = () => {
  const { pathname } = useLocation();
  useEffect(() => {
    const path = pathname.length > 1 ? pathname.replace(/\/$/, "") : "/";
    const page = PAGES[path];
    const [title, desc] = page || DEFAULT;
    const full = path === "/" ? `${BRAND} | ${title}` : `${title} | ${BRAND}`;
    document.title = full;
    setMeta("name", "description", desc);
    setMeta("name", "robots", page ? "index, follow" : "noindex, nofollow");
    setMeta("property", "og:title", full);
    setMeta("property", "og:description", desc);
    setMeta("property", "og:url", `${SITE}${path === "/" ? "/" : path}`);
    setCanonical(`${SITE}${path === "/" ? "/" : path}`);
  }, [pathname]);
  return null;
};
