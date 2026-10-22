import { test, expect } from "../support";
import { doc_room_joined, doctype_room_joined, realtime_connected } from "../support/realtime";

test.describe("Realtime updates", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await realtime_connected(page);
		await desk.clear_filters();
	});

	test("Shows version conflict warning", async ({ page, desk, api }) => {
		const doc = await api.insert_doc("ToDo", { description: "old" });
		await page.goto(`/desk/todo/${doc.name}`);
		await realtime_connected(page);
		await doc_room_joined(page, api, "ToDo", doc.name);
		await desk.fill_field("status", "Cancelled", "Select");

		await api.update_doc("ToDo", doc.name, { status: "Closed" });
		await page.getByRole("button", { name: "Refresh", exact: true }).click();
		await expect(desk.get_field("status", "Select")).toHaveValue("Closed");
	});

	test("List view updates in realtime on insert", async ({ page, api }) => {
		const original = "Added for realtime update";
		const updated = "Updated for realtime update";
		await doctype_room_joined(page, api, "ToDo");
		const doc = await api.insert_doc("ToDo", { description: original });
		await expect(page.getByText(original).first()).toBeVisible();

		await api.update_doc("ToDo", doc.name, { description: updated });
		await expect(page.getByText(updated).first()).toBeVisible();
	});

	test("Receives msgprint from server", async ({ page, api }) => {
		const msg = "msgprint sent via realtime";
		await api.call("frappe.tests.ui_test_helpers.publish_realtime", {
			event: "msgprint",
			message: msg,
		});
		await expect(page.getByText(msg).first()).toBeVisible();
	});

	test("Recieves custom messages from server", async ({ page, api }) => {
		const event = "playwright_event";
		await page.evaluate((event) => {
			window.realtime_event_received = false;
			frappe.realtime.on(event, () => {
				window.realtime_event_received = true;
			});
		}, event);

		await api.call("frappe.tests.ui_test_helpers.publish_realtime", { event });
		await expect.poll(() => page.evaluate(() => window.realtime_event_received)).toBe(true);
	});

	test("Progress bar", async ({ page, api }) => {
		const title = "RealTime Progress";
		await api.call("frappe.tests.ui_test_helpers.publish_progress", { title });
		await expect(page.getByText(title).first()).toBeVisible();
	});
});
