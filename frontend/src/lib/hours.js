export const WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const defaultHours = () => WEEK.map((day) => ({ day, open: false, from: "08:00", to: "18:00" }));

const slot = (d) => (d.open ? `${d.from}-${d.to}` : "Closed");

export const hoursText = (oh) => {
  if (!oh?.some((d) => d.open)) return "";
  const groups = [];
  oh.forEach((d) => {
    const last = groups[groups.length - 1];
    if (last && slot(last.end) === slot(d)) last.end = d;
    else groups.push({ start: d, end: d });
  });
  return groups.map((g) => `${g.start.day.slice(0, 3)}${g.start === g.end ? "" : `-${g.end.day.slice(0, 3)}`} ${slot(g.start)}`).join(" · ");
};

export const hoursSchema = (oh) => (oh || []).filter((d) => d.open).map((d) => ({
  "@type": "OpeningHoursSpecification", dayOfWeek: `https://schema.org/${d.day}`, opens: d.from, closes: d.to,
}));
