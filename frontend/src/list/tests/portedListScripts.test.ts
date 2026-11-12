// The list.js files ported from desk v1's *_list.js: what each badge and row action gives a row.
import { resetSession, setSession } from "@framework/ui/useSession";
import { afterEach, describe, expect, it, vi } from "vitest";

import activityLog from "../../../../frappe/core/doctype/activity_log/frontend/list.js";
import autoRepeat from "../../../../frappe/automation/doctype/auto_repeat/frontend/list.js";
import triggerQueue from "../../../../frappe/automation/doctype/automation_trigger_queue/frontend/list.js";
import customSidebar from "../../../../frappe/desk/doctype/custom_sidebar/frontend/list.js";
import todo from "../../../../frappe/desk/doctype/todo/frontend/list.js";
import webFormRequest from "../../../../frappe/website/doctype/web_form_request/frontend/list.js";

afterEach(() => resetSession());

function systemZone(timezone: string) {
	setSession({ user: {}, roles: [], lang: "en", timezone, defaults: {} } as never);
}

function systemTime(offsetHours: number) {
	const at = new Date(Date.now() + offsetHours * 3600_000).toISOString();
	return at.slice(0, 19).replace("T", " ");
}

function fakePage() {
	const columns: Record<string, any> = {};
	const rowActions: any[] = [];
	return {
		columns: { update: (field: string, cell: any) => (columns[field] = cell) },
		rowActions: { add: (item: any) => rowActions.push(item) },
		open: vi.fn(),
		cells: columns,
		actions: rowActions,
	};
}

function cellOf(script: { onRefresh(page: any): void }, field: string) {
	const page = fakePage();
	script.onRefresh(page);
	return page.cells[field];
}

describe("ported list scripts", () => {
	it("Auto Repeat colours its status and filters by it", () => {
		const badge = cellOf(autoRepeat, "status").badge;
		expect(badge({ status: "Disabled" })).toEqual({
			label: "Disabled",
			theme: "red",
			filters: [["status", "=", "Disabled"]],
		});
		expect(badge({ status: "" })).toBeFalsy();
	});

	it("Automation Trigger Queue shows when a scheduled run starts", () => {
		const cell = cellOf(triggerQueue, "status");
		expect(cell.fields).toEqual(["run_after"]);
		const scheduled = cell.badge({ status: "Scheduled", run_after: "2026-11-12 10:30:00" });
		expect(scheduled.label).toMatch(/^Scheduled for .*2026/);
		expect(scheduled.theme).toBe("blue");
		expect(cell.badge({ status: "Failed" }).theme).toBe("red");
	});

	it("Activity Log marks only login rows", () => {
		const badge = cellOf(activityLog, "status").badge;
		expect(badge({ operation: "Login", status: "Failed" })).toEqual({ label: "Failed", theme: "red" });
		expect(badge({ operation: "Logout", status: "Success" })).toBeFalsy();
	});

	it("Custom Sidebar marks a sidebar with no user as the site's", () => {
		const badge = cellOf(customSidebar, "user").badge;
		expect(badge({ user: null }).label).toBe("Site");
		expect(badge({ user: "a@example.com" })).toBeFalsy();
	});

	it("Web Form Request tells used, expired and unused requests apart", () => {
		const badge = cellOf(webFormRequest, "first_used_on").badge;
		expect(badge({ first_used_on: "2026-11-01 09:00:00" }).label).toBe("Used");
		expect(badge({ expires_on: "2000-01-01 00:00:00" }).label).toBe("Expired");
		expect(badge({ expires_on: "2999-01-01 00:00:00" }).label).toBe("Not Used");
	});

	it("Automation Trigger Queue reads run_after on the system clock", () => {
		systemZone("Asia/Kolkata");
		const badge = cellOf(triggerQueue, "status").badge;
		const when = new Date(Date.UTC(2026, 10, 12, 5, 0)).toLocaleString(undefined, {
			dateStyle: "medium",
			timeStyle: "short",
		});
		expect(badge({ status: "Scheduled", run_after: "2026-11-12 10:30:00" }).label).toBe(
			`Scheduled for ${when}`,
		);
	});

	it("Web Form Request reads expires_on on the system clock", () => {
		const badge = cellOf(webFormRequest, "first_used_on").badge;
		// One hour from now as UTC wall time: still ahead at UTC-10, already past at UTC+14.
		const expiresOn = systemTime(1);
		systemZone("Pacific/Honolulu");
		expect(badge({ expires_on: expiresOn }).label).toBe("Not Used");
		systemZone("Pacific/Kiritimati");
		const expired = badge({ expires_on: expiresOn });
		expect(expired.label).toBe("Expired");
		expect(expired.filters[0]).toEqual(["first_used_on", "is", "not set"]);
		expect(expired.filters[1][0]).toBe("expires_on");
	});

	it("ToDo opens its reference from the row menu", () => {
		const page = fakePage();
		todo.onRefresh(page);
		const [action] = page.actions;
		expect(action.when(page, { reference_type: "Note", reference_name: "N-1" })).toBe(true);
		expect(action.when(page, { reference_type: "Note" })).toBe(false);
		action.run(page, { reference_type: "Note", reference_name: "N-1" });
		expect(page.open).toHaveBeenCalledWith("Note", "N-1");
	});
});
