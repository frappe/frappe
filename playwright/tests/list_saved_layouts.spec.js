import { test, expect } from "../support";

const LIST_URL = "/desk/todo";
const VIEW_SWITCHER = ".custom-btn-group.view-switcher button:visible";

const menu_item = (page, label) => page.locator(".es-menu__item", { hasText: label }).first();

// saved layouts live in the view switcher: the current view's row
// ("List View") carries them as an async submenu
async function open_layout_submenu(page) {
	await page.locator(VIEW_SWITCHER).click();
	await menu_item(page, "List View").hover();
	await expect(menu_item(page, "Default Layout")).toBeAttached();
}

async function select_layout(page, label) {
	await open_layout_submenu(page);
	const preference_saved = page.waitForResponse((res) =>
		res.url().includes("/api/method/frappe.model.utils.user_settings.save")
	);
	await menu_item(page, label).click();
	await preference_saved;
}

// the switcher trigger shows the active layout name (or "List View" when
// the default layout is active)
async function assert_active_layout(page, label) {
	const trigger_label = label === "Default Layout" ? "List View" : label;
	await expect(page.locator(VIEW_SWITCHER)).toContainText(trigger_label);
}

function create_test_layout(api, args = {}) {
	return api.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", args);
}

const fetch_fields = (page) => page.evaluate(() => (cur_list.fields || []).map((f) => f[0]));

test.describe("List View — Saved Layouts", () => {
	test.beforeEach(async ({ api }) => {
		await api.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
	});

	test("restores last selected layout on a clean URL when no URL filters exist", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_empty",
			filters: "[]",
		});

		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();

		await select_layout(page, "_test_layout_empty");
		await assert_active_layout(page, "_test_layout_empty");

		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();

		await assert_active_layout(page, "_test_layout_empty");
	});

	test("does not auto-apply empty-filter layout from URL signature alone", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_empty",
			filters: "[]",
		});

		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();

		await assert_active_layout(page, "Default Layout");
	});

	test("auto-applies a layout when the URL matches its route signature", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_open",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		await page.goto(`${LIST_URL}?status=Open`);
		await desk.ready();

		await assert_active_layout(page, "_test_layout_open");
	});

	test("applies a saved layout from the menu and can switch back to default", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_switch",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();

		await select_layout(page, "_test_layout_switch");
		await assert_active_layout(page, "_test_layout_switch");

		await select_layout(page, "Default Layout");
		await assert_active_layout(page, "Default Layout");
	});

	test("opens manage layouts dialog with the saved layout listed", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_manage",
		});

		await page.goto(LIST_URL);
		await desk.ready();

		await open_layout_submenu(page);
		await menu_item(page, "Manage Layouts").click();

		await expect(page.locator(".modal-dialog:visible")).toContainText("Manage Layouts");
		const layout_row = page.locator(".layout-manage-row");
		await expect(layout_row.filter({ hasText: "_test_layout_manage" }).first()).toBeVisible();
		await expect(layout_row.filter({ hasText: "Personal" }).first()).toBeVisible();
	});

	test("switches to list view with a layout applied, from another view", async ({
		page,
		desk,
		api,
	}) => {
		await create_test_layout(api, {
			layout_name: "_test_layout_jump",
			filters: JSON.stringify([["ToDo", "status", "=", "Open"]]),
			route_signature: "status=Open",
		});

		await page.goto(`${LIST_URL}/view/report`);
		await desk.ready();

		await page.locator(VIEW_SWITCHER).click();
		await menu_item(page, "List View").hover();
		await menu_item(page, "_test_layout_jump").click();

		await expect.poll(() => page.evaluate(() => cur_list.view_name)).toBe("List");
		await assert_active_layout(page, "_test_layout_jump");
	});

	test("fetches non-in_list_view fields used as saved layout columns", async ({
		page,
		desk,
		api,
	}) => {
		// `role` is on ToDo but not in_list_view — layout columns must still be fetched.
		await create_test_layout(api, {
			layout_name: "_test_layout_columns",
			filters: "[]",
			columns: JSON.stringify([
				{ fieldname: "description", label: "Description" },
				{ fieldname: "status_field", label: "Status" },
				{ fieldname: "role", label: "Role" },
			]),
		});
		await create_test_layout(api, {
			layout_name: "_test_layout_no_role",
			filters: "[]",
			columns: JSON.stringify([
				{ fieldname: "description", label: "Description" },
				{ fieldname: "status_field", label: "Status" },
				{ fieldname: "priority", label: "Priority" },
			]),
		});

		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();

		await select_layout(page, "_test_layout_columns");
		await assert_active_layout(page, "_test_layout_columns");

		await expect.poll(() => fetch_fields(page)).toContain("role");
		await expect
			.poll(() =>
				page.evaluate(() =>
					(cur_list.columns || [])
						.filter((col) => col.df?.fieldname)
						.map((col) => col.df.fieldname)
				)
			)
			.toContain("role");

		await select_layout(page, "_test_layout_no_role");
		await assert_active_layout(page, "_test_layout_no_role");

		await expect.poll(() => fetch_fields(page)).not.toContain("role");
		expect(await fetch_fields(page)).toContain("priority");
	});
});
