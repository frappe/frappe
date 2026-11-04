// The one reading of "3 days ago" behind list cells and the index's recent list.
import { resetSession, setSession } from "../useSession";
import { dayjs } from "frappe-ui";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { relativeTime, siteTime } from "../relativeTime";

const NOW = "2026-11-04T04:30:00Z";

function readAs(lang: string, offsetMs: number) {
	setSession({ user: {}, roles: [], lang, timezone: "Asia/Kolkata", defaults: {} } as never);
	return relativeTime(dayjs(new Date(Date.parse(NOW) + offsetMs)));
}

describe("relativeTime", () => {
	beforeEach(() => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date(NOW));
	});

	afterEach(() => {
		vi.useRealTimers();
		resetSession();
	});

	it("reads a stamp less than a minute ahead as a few seconds ago, and keeps a real future", () => {
		expect(readAs("en", 59_000)).toBe("a few seconds ago");
		expect(readAs("en", 1_000)).toBe("a few seconds ago");
		expect(readAs("en", -20_000)).toBe("a few seconds ago");
		expect(readAs("en", 2 * 60_000)).toBe("in 2 minutes");
		expect(readAs("en", 2 * 3_600_000)).toBe("in 2 hours");
		expect(readAs("en", -3 * 86_400_000)).toBe("3 days ago");
	});

	it("reads in the signed-in person's language", () => {
		expect(readAs("de", -3 * 60_000)).toBe("vor 3 Minuten");
		expect(readAs("de", -3 * 86_400_000)).toBe("vor 3 Tagen");
		expect(readAs("de", 2 * 3_600_000)).toBe("in 2 Stunden");
		expect(readAs("hi", -2 * 3_600_000)).toBe("2 घंटे पहले");
		expect(readAs("pt-BR", -40 * 86_400_000)).toBe("há 1 mês");
		expect(readAs("de", -400 * 86_400_000)).toBe("vor 1 Jahr");
	});

	it("clamps the skew in every language", () => {
		expect(readAs("de", 30_000)).toBe("jetzt");
		expect(readAs("de", 90_000)).toBe("in 2 Minuten");
	});

	it("reads a stamp the same distance back and ahead alike, at the unit breakpoints", () => {
		expect(readAs("de", -90_000)).toBe("vor 2 Minuten");
		expect(readAs("de", 90_000)).toBe("in 2 Minuten");
		expect(readAs("de", -44_000)).toBe("jetzt");
		expect(readAs("de", -46_000)).toBe("vor 1 Minute");
		expect(readAs("de", 60_000)).toBe("in 1 Minute");
		expect(readAs("de", -46 * 60_000)).toBe("vor 1 Stunde");
		expect(readAs("de", -23 * 3_600_000)).toBe("vor 1 Tag");
		expect(readAs("de", -27 * 86_400_000)).toBe("vor 1 Monat");
		expect(readAs("de", 400 * 86_400_000)).toBe("in 1 Jahr");
	});

	it("speaks English for a regional English code, and Serbian Latin for sr-CS", () => {
		expect(readAs("en-GB", -3 * 60_000)).toBe("3 minutes ago");
		expect(readAs("en_US", -3 * 60_000)).toBe("3 minutes ago");
		expect(readAs("sr-CS", -3 * 86_400_000)).toBe("pre 3 dana");
		expect(readAs("zh-TW", -3 * 86_400_000)).toBe("3 天前");
	});

	it("reads an invalid stamp as nothing, whatever the language", () => {
		expect(readAs("de", NaN)).toBe("");
		expect(readAs("en", NaN)).toBe("");
	});

	it("falls back to English without a session, and for a language the browser does not know", () => {
		resetSession();
		expect(relativeTime(dayjs(new Date(Date.parse(NOW) - 3 * 60_000)))).toBe("3 minutes ago");
		expect(readAs("not a language!", -3 * 60_000)).toBe("3 minutes ago");
	});
});

describe("siteTime", () => {
	beforeEach(() => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date(NOW));
	});

	afterEach(() => {
		vi.useRealTimers();
		resetSession();
	});

	// The test runner's zone is UTC; the site is five and a half hours ahead of it.
	function onSite(zone: string | undefined) {
		setSession({ user: {}, roles: [], lang: "en", timezone: zone, defaults: {} } as never);
	}

	it("reads a stored stamp on the site's clock, not the browser's", () => {
		onSite("Asia/Kolkata");
		// 10:00 in Kolkata is 04:30 UTC, "now" in this test.
		expect(siteTime("2026-11-04 10:00:00").toISOString()).toBe("2026-11-04T04:30:00.000Z");
		expect(relativeTime(siteTime("2026-11-04 09:59:40"))).toBe("a few seconds ago");
		expect(relativeTime(siteTime("2026-11-04 07:30:00"))).toBe("3 hours ago");
	});

	it("keeps the site's wall clock in the absolute form", () => {
		onSite("Asia/Kolkata");
		expect(siteTime("2026-11-04 10:00:00").format("YYYY-MM-DD HH:mm")).toBe("2026-11-04 10:00");
	});

	it("reads in the browser's zone when the session has none", () => {
		onSite(undefined);
		expect(siteTime("2026-11-04 10:00:00").valueOf()).toBe(new Date(2026, 10, 4, 10).getTime());
	});

	it("keeps the instant of a stamp that names its own zone", () => {
		onSite("Asia/Kolkata");
		expect(siteTime("2026-11-04T10:00:00Z").toISOString()).toBe("2026-11-04T10:00:00.000Z");
		expect(siteTime("2026-11-04T10:00:00+05:30").toISOString()).toBe("2026-11-04T04:30:00.000Z");
	});

	it("reads a date alone as midnight on the site's clock", () => {
		onSite("Asia/Kolkata");
		expect(siteTime("2026-11-04").toISOString()).toBe("2026-11-03T18:30:00.000Z");
	});

	it("leaves a stamp it cannot read invalid, so nothing is drawn", () => {
		onSite("Asia/Kolkata");
		expect(siteTime("garbage").isValid()).toBe(false);
		expect(relativeTime(siteTime("garbage"))).toBe("");
	});
});
