// The timeline's times read a stored stamp on the site's clock, whatever zone the browser is in.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSession, setSession } from "../../../composables/useSession";
import { dateFormat, timeAgo } from "../utils";

// 04:30 UTC is 10:00 in Kolkata, five and a half hours ahead of the browser (UTC) in this run.
const NOW = "2026-11-04T04:30:00Z";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(NOW));
  setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
});

afterEach(() => {
  vi.useRealTimers();
  resetSession();
});

describe("timeline times", () => {
  it("reads a fresh stamp as just now, not hours ahead", () => {
    expect(timeAgo("2026-11-04 09:59:50")).toBe("a few seconds ago");
  });

  it("reads an older stamp from the site's clock", () => {
    expect(timeAgo("2026-11-04 07:30:00")).toBe("3 hours ago");
  });

  it("draws the absolute form on the site's clock", () => {
    expect(dateFormat("2026-11-04 10:00:00")).toBe("Wed, Nov 4, 2026 10:00 AM");
  });

  it("draws nothing without a stamp", () => {
    expect(timeAgo()).toBe("");
    expect(dateFormat()).toBe("");
  });
});
