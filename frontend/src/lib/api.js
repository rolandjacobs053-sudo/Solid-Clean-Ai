import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

export const gbp = (n) =>
  n == null ? "—" : `${Number(n) < 0 ? "-" : ""}£${Math.abs(Number(n)).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const fmtDate = (iso) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export const label = (s) => (s ? String(s).replace(/_/g, " ") : "—");

export const SOURCES = ["website", "seo", "google_ads", "ai_chat", "phone", "cold_email", "referral", "whatsapp", "other"];

export function getSource() {
  const saved = sessionStorage.getItem("sc_source");
  if (saved) return saved;
  const p = new URLSearchParams(window.location.search);
  const utm = `${p.get("utm_source") || ""} ${p.get("utm_medium") || ""}`.toLowerCase();
  let s = "website";
  if (p.get("gclid") || /cpc|google_?ads|adwords/.test(utm)) s = "google_ads";
  else if (utm.trim()) s = utm.includes("email") ? "cold_email" : utm.includes("whatsapp") ? "whatsapp" : utm.includes("google") ? "seo" : "referral";
  else if (/google\.|bing\.|duckduckgo|yahoo\./.test(document.referrer)) s = "seo";
  sessionStorage.setItem("sc_source", s);
  return s;
}
