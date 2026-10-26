import type { Cafeteria } from "@uniserve/shared-types";

/** Preserve the manual status, but never advertise opening outside published hours. */
export function withCurrentHours(cafeteria: Cafeteria, now = new Date()): Cafeteria {
  if (cafeteria.operational_status !== "open") return cafeteria;
  const match = cafeteria.operating_hours?.match(/^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/);
  if (!match) return cafeteria;
  const [, h1, m1, h2, m2] = match.map(Number);
  if (h1 > 23 || h2 > 23 || m1 > 59 || m2 > 59) return cafeteria;
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: cafeteria.timezone || "Asia/Karachi", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(now);
    const minute = Number(parts.find(p => p.type === "hour")?.value) * 60 + Number(parts.find(p => p.type === "minute")?.value);
    const start = h1 * 60 + m1, end = h2 * 60 + m2;
    const open = start < end ? minute >= start && minute < end : minute >= start || minute < end;
    return open ? cafeteria : { ...cafeteria, operational_status: "closed" };
  } catch { return cafeteria; }
}
