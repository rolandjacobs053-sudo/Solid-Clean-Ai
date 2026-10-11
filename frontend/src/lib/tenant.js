import { useParams } from "react-router-dom";

export const DEFAULT_SLUG = "solid-clean";

export const useTenant = () => {
  const { slug: param } = useParams();
  const slug = param || DEFAULT_SLUG;
  return { slug, base: param ? `/c/${slug}` : "", pub: `/public/${slug}` };
};

export const FEATURES = [
  ["quotes_bookings", "Automated quotes & online bookings"], ["crm", "CRM & customer management"], ["analytics", "Business analytics"],
  ["ai_receptionist", "AI receptionist"], ["reviews", "Review management"], ["outreach", "Cold email outreach"], ["marketing", "SEO & Google Ads tools"],
];
