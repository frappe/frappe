import { afterEach, describe, expect, it, vi } from "vitest";
import { resetSession, setSession } from "@framework/ui/useSession";
import { isSwitchCell, resolveCell } from "../cells";

afterEach(() => resetSession());

describe("resolveCell", () => {
	it("picks a value's icon, dropping frappe-ui's prefix, or its badge theme", () => {
		expect(resolveCell({ icons: { Done: "lucide-circle-check" } }, "Done", "Select")).toEqual({ icon: "circle-check" });
		expect(resolveCell({ badge: { High: "red" } }, "High", "Select")).toEqual({ theme: "red" });
		expect(resolveCell({ badge: { Medium: "orange" } }, "Medium", "Select")).toEqual({ theme: "amber" });
	});

	it("names nothing for an unknown value, an empty one or no entry", () => {
		const cell = { icons: { Done: "circle" }, icon: "calendar" };
		expect(resolveCell(cell, "Todo", "Select")).toEqual({ icon: "calendar" });
		expect(resolveCell(cell, "", "Select")).toBeNull();
		expect(resolveCell(cell, null, "Select")).toBeNull();
		expect(resolveCell(undefined, "Done", "Select")).toBeNull();
		expect(resolveCell({ badge: { High: "red" } }, "Low", "Select")).toBeNull();
	});

	it("formats a Date or Datetime and gives the full date as its title", () => {
		const cell = { icon: "lucide-calendar", format: "D MMM, hh:mm a" };
		expect(resolveCell(cell, "2026-10-25 00:00:00", "Datetime")).toEqual({
			icon: "calendar",
			text: "25 Oct, 12:00 am",
			title: "Sun, Oct 25, 2026 | 12:00 am",
		});
		expect(resolveCell({ format: "D MMM" }, "2026-10-25", "Date")).toEqual({
			icon: undefined,
			text: "25 Oct",
			title: "Sun, Oct 25, 2026",
		});
	});

	it("reads a Datetime in the session's zone", () => {
		const cell = { format: "HH:mm Z" };
		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		expect(resolveCell(cell, "2026-10-25 23:00:00", "Datetime")?.text).toBe("23:00 +05:30");
		setSession({ user: {}, roles: [], lang: "en", timezone: "America/New_York", defaults: {} } as never);
		expect(resolveCell(cell, "2026-10-25 23:00:00", "Datetime")?.text).toBe("23:00 -04:00");
	});

	it("names nothing for an inherited key or a field a cell of its own draws", () => {
		expect(resolveCell({ badge: { High: "red" } }, "constructor", "Select")).toBeNull();
		expect(resolveCell({ icons: { 1: "circle" }, icon: "star" }, 1, "Rating")).toBeNull();
	});

	it("ignores a format on another fieldtype or a value that is no date", () => {
		expect(resolveCell({ format: "D MMM" }, "Done", "Select")).toBeNull();
		expect(resolveCell({ format: "D MMM" }, "not a date", "Date")).toBeNull();
		expect(resolveCell({ icon: "calendar", format: "D MMM" }, "Done", "Select")).toEqual({ icon: "calendar" });
	});
});

describe("resolveCell with a badge function", () => {
	const row = { status: "Open", overdue: 1 };

	it("draws what the function returns for the row, its label and filters kept", () => {
		const badge = () => ({ label: "Overdue", theme: "orange" as const, filters: [["overdue", "=", 1]] as [string, string, unknown][] });
		expect(resolveCell({ badge }, "Open", "Select", row)).toEqual({
			theme: "amber",
			label: "Overdue",
			filters: [["overdue", "=", 1]],
		});
		expect(resolveCell({ badge: () => ({ theme: "red" }) }, "Open", "Select", row)).toEqual({ theme: "red" });
	});

	it("answers for an empty value, since it reads the row", () => {
		const badge = (one: Record<string, any>) => (one.overdue ? { label: "Overdue", theme: "red" as const } : null);
		expect(resolveCell({ badge }, "", "Data", row)).toEqual({ theme: "red", label: "Overdue" });
		expect(resolveCell({ badge }, null, "Data", { overdue: 0 })).toBeNull();
	});

	it("falls to the default cell when it returns nothing, a non-object, or throws", () => {
		const log = vi.spyOn(console, "error").mockImplementation(() => {});
		expect(resolveCell({ badge: () => null }, "Open", "Select", row)).toBeNull();
		expect(resolveCell({ badge: () => undefined }, "Open", "Select", row)).toBeNull();
		expect(resolveCell({ badge: () => "red" as never }, "Open", "Select", row)).toBeNull();
		expect(
			resolveCell({ badge: () => { throw new Error("boom"); } }, "Open", "Select", row)
		).toBeNull();
		expect(log).toHaveBeenCalledTimes(1);
		log.mockRestore();
	});

	it("keeps a cell's own icon for a value when the function names nothing, and a gray theme by default", () => {
		expect(resolveCell({ badge: () => null, icons: { Open: "circle" } }, "Open", "Select", row)).toEqual({ icon: "circle" });
		expect(resolveCell({ badge: () => ({}) }, "Open", "Select", row)).toEqual({ theme: "gray" });
	});

	it("falls to gray for an unknown theme and drops malformed filters, keeping the badge", () => {
		const badge = () => ({ theme: "purple", filters: [["status", "="]] }) as never;
		expect(resolveCell({ badge }, "Open", "Select", row)).toEqual({ theme: "gray" });
	});

	it("leaves a field with a cell of its own to that cell", () => {
		expect(resolveCell({ badge: () => ({ theme: "red" }) }, 1, "Check", row)).toBeNull();
	});
});

describe("isSwitchCell", () => {
	it("draws only a Check column an app marked as a switch", () => {
		expect(isSwitchCell({ switch: true }, "Check")).toBe(true);
		expect(isSwitchCell({ switch: true }, "Data")).toBe(false);
		expect(isSwitchCell({ icon: "lucide-circle" }, "Check")).toBe(false);
		expect(isSwitchCell(undefined, "Check")).toBe(false);
	});
});
