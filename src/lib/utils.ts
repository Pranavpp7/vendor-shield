import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** URL-safe slug from vendor name (e.g. "ServiceNow" → "servicenow", "SAP" → "sap"). */
export function vendorNameToSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

/** Parse a stored timestamp safely.  Records hold either full ISO strings
 *  ("2026-07-05T03:08:28.544098+00:00") or date-only strings ("2026-07-07").
 *  Date-only MUST be parsed as a LOCAL date — new Date("2026-07-07") is UTC
 *  midnight, which renders as the previous day in negative-offset timezones. */
function parseStoredDate(value: string): Date | null {
  if (!value) return null;
  const dateOnly = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const d = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

/** "Jul 5, 2026" — for tables and compact displays. */
export function formatDate(value: string): string {
  const d = parseStoredDate(value);
  if (!d) return value || "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** "Jul 5, 2026, 3:08 AM" — where the time matters (detail header). */
export function formatDateTime(value: string): string {
  const d = parseStoredDate(value);
  if (!d) return value || "—";
  // Date-only strings have no meaningful time — don't invent midnight
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}
