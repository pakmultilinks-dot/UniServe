import { withCurrentHours } from "../services/cafeteria-hours";
import type { Cafeteria } from "@uniserve/shared-types";
const cafe = { operating_hours: "07:00-16:00", timezone: "Asia/Karachi", operational_status: "open" } as Cafeteria;
it.each([
  ["2026-10-26T01:59:00Z", "closed"],
  ["2026-10-26T02:00:00Z", "open"],
  ["2026-10-26T10:59:00Z", "open"],
  ["2026-10-26T11:00:00Z", "closed"],
  ["2026-10-26T12:48:00Z", "closed"],
])("honors local opening/closing boundary %s", (time, expected) => {
  expect(withCurrentHours(cafe, new Date(time)).operational_status).toBe(expected);
});
it("preserves manual closure during published hours", () => {
  expect(withCurrentHours({ ...cafe, operational_status: "closed" }, new Date("2026-10-26T05:00:00Z")).operational_status).toBe("closed");
});
it("supports missing legacy hours without inventing a schedule", () => {
  expect(withCurrentHours({ ...cafe, operating_hours: undefined })).toEqual({ ...cafe, operating_hours: undefined });
});
