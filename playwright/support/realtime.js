import { expect } from "@playwright/test";

const PROBE_EVENT = "playwright_room_probe";

export function realtime_connected(page) {
	return page.waitForFunction(() => window.frappe?.realtime?.socket?.connected);
}

// The server joins a doctype/doc room only after an async permission check and never
// acknowledges it, so publish to the room until an event comes back through it.
async function room_joined(page, api, target) {
	await page.evaluate((event) => {
		window.realtime_room_joined = false;
		frappe.realtime.on(event, () => {
			window.realtime_room_joined = true;
		});
	}, PROBE_EVENT);

	await expect(async () => {
		await api.call("frappe.tests.ui_test_helpers.publish_realtime", {
			event: PROBE_EVENT,
			...target,
		});
		await expect
			.poll(() => page.evaluate(() => window.realtime_room_joined), { timeout: 1000 })
			.toBe(true);
	}).toPass({ timeout: 20000 });
}

export function doctype_room_joined(page, api, doctype) {
	return room_joined(page, api, { room: `doctype:${doctype}` });
}

export function doc_room_joined(page, api, doctype, docname) {
	return room_joined(page, api, { doctype, docname: String(docname) });
}
