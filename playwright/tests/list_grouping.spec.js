import { test, expect } from "../support";

const TAG = "_test_grouping";
const LIST_URL = `/desk/todo?description=${encodeURIComponent(`["like","%${TAG}%"]`)}`;
const VIEW_SWITCHER = ".custom-btn-group.view-switcher button:visible";

const group_button = (page) => page.locator(".list-group-selector .es-button").first();
const group_rows = (page) => page.locator('.list-group-section[data-depth="0"] > .list-group-row');
const menu_item = (page, label) => page.locator(".es-menu__item", { hasText: label }).first();

async function select_layout(page, label) {
	await page.locator(VIEW_SWITCHER).click();
	await menu_item(page, "List View").hover();
	const preference_saved = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.model.utils.user_settings.save")
	);
	await menu_item(page, label).click();
	await preference_saved;
}

test.describe("List View — Grouping", () => {
	let todos = [];

	test.beforeEach(async ({ api }) => {
		await api.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
		todos = [];
		for (const [status, priority] of [
			["Open", "High"],
			["Open", "Low"],
			["Closed", "Low"],
		]) {
			const doc = await api.insert_doc("ToDo", {
				description: `${TAG} ${status} ${priority}`,
				status,
				priority,
			});
			todos.push(doc.name);
		}
	});

	test.afterEach(async ({ api }) => {
		for (const name of todos) await api.remove_doc("ToDo", name, true);
		await api.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
		// the page's filter is kept for the Default layout
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings", {
			clear_filters: 1,
		});
	});

	test("groups from the Group button, opens a group and keeps the grouping per layout", async ({
		page,
		desk,
		api,
	}) => {
		// its filters differ from the page's, so it isn't picked up from the URL
		await api.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", {
			layout_name: "_test_layout_by_priority",
			filters: JSON.stringify([
				["ToDo", "description", "like", `%${TAG}%`],
				["ToDo", "status", "!=", "Cancelled"],
			]),
			grouping: JSON.stringify({ levels: [{ fieldname: "priority", order: "value-asc" }] }),
		});

		await page.goto(LIST_URL);
		await desk.ready();

		await group_button(page).click();
		await page.locator(".group-editor-popover button", { hasText: "Status" }).first().click();
		await page.keyboard.press("Escape");
		await expect(group_button(page)).toHaveText("Status");
		await expect(group_rows(page)).toHaveCount(2);
		await expect(page.locator(".list-count")).toHaveText("2 groups");

		await group_rows(page).filter({ hasText: "Open" }).click();
		await expect(page.locator(".list-group-body .list-row-checkbox")).toHaveCount(2);

		// the Default layout keeps it in user settings
		await page.reload();
		await desk.ready();
		await expect(group_button(page)).toHaveText("Status");

		// a saved layout brings its own grouping; Default gets its own back
		await select_layout(page, "_test_layout_by_priority");
		await expect(group_button(page)).toHaveText("Priority");
		await expect(group_rows(page)).toHaveCount(2);
		await select_layout(page, "Default Layout");
		await expect(group_button(page)).toHaveText("Status");

		await page.locator(".list-group-selector .es-button").nth(1).click();
		await expect(group_button(page)).toHaveText("Group");
		await expect(page.locator(".list-group-section")).toHaveCount(0);
	});
});
