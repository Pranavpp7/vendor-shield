import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime } from "./utils";

describe("formatDate", () => {
  it("formats full ISO timestamps", () => {
    expect(formatDate("2026-07-05T03:08:28.544098+00:00")).toMatch(/Jul \d{1,2}, 2026/);
  });

  it("parses date-only strings as LOCAL dates (no off-by-one in negative offsets)", () => {
    // Regression: new Date("2026-07-07") is UTC midnight, which renders as
    // July 6 in US timezones. Our parser must keep it July 7 everywhere.
    expect(formatDate("2026-07-07")).toBe("Jul 7, 2026");
  });

  it("passes through unparseable values instead of showing 'Invalid Date'", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
    expect(formatDate("")).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("includes the time for full timestamps", () => {
    expect(formatDateTime("2026-07-05T15:08:28+00:00")).toMatch(/2026.*\d{1,2}:\d{2}/);
  });

  it("omits a fabricated midnight for date-only strings", () => {
    expect(formatDateTime("2026-07-07")).toBe("Jul 7, 2026");
  });
});
