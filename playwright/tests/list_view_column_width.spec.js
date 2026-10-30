import { test, expect } from "../support";

const DOCTYPE = "DocType";
const LIST_URL = "/desk/List/DocType/List";
const SAVE_SETTINGS =
	"frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings";

// Columns with a fixed starting width so drag tests have a predictable baseline
// and never start at the natural flexbox width (which can vary by viewport).
const BASE_FIELDS = JSON.stringify([
	{ fieldname: "name", label: "Name" },
	{ fieldname: "module", label: "Module", width: 150 },
]);

async function open_list_settings(page, desk) {
	await desk.click_menu_button("List Settings");
	await expect(page.locator(".modal-dialog:visible")).toContainText(
		`${DOCTYPE} List View Settings`
	);
}

function save_list_view_settings(api, fields) {
	return api.call(SAVE_SETTINGS, {
		doctype: DOCTYPE,
		listview_settings: { fields },
		removed_listview_fields: [],
	});
}

function get_column_width(page, fieldname) {
	return page
		.locator(`.list-row-head .list-row-col[data-fieldname="${fieldname}"]`)
		.evaluate((el) => $(el).outerWidth());
}

// Simulate drag-to-resize using jQuery $.Event so that both the delegated
// mousedown handler on $result and the document-level mousemove/mouseup
// handlers receive events with the right pageX values. Dropping the handle
// saves the new width, so wait for that save to land.
async function drag_resize_column(page, fieldname, delta_x) {
	const settings_saved = page.waitForResponse((res) => res.url().includes(SAVE_SETTINGS));
	await page.evaluate(
		([fieldname, delta_x]) => {
			const handle = document.querySelector(
				`.list-row-head .list-row-col[data-fieldname="${fieldname}"] .list-col-resize-handle`
			);
			if (!handle) throw new Error(`Resize handle for "${fieldname}" not found`);

			const rect = handle.getBoundingClientRect();
			const start_x = rect.left + rect.width / 2;

			$(handle).trigger($.Event("mousedown", { pageX: start_x, which: 1, button: 0 }));
			$(document).trigger($.Event("mousemove", { pageX: start_x + delta_x }));
			$(document).trigger($.Event("mouseup", { pageX: start_x + delta_x }));
		},
		[fieldname, delta_x]
	);
	await settings_saved;
}

test.describe("List View — Column Widths", () => {
	test.beforeEach(async ({ page, desk, api }) => {
		await save_list_view_settings(api, BASE_FIELDS);
		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();
	});

	test("saves and applies column width set in List View Settings dialog", async ({
		page,
		desk,
	}) => {
		await open_list_settings(page, desk);

		const width_input = page.locator(
			'.modal-dialog:visible [data-fieldname="module"] input.form-control'
		);
		await width_input.clear();
		await width_input.pressSequentially("180");

		await page.getByRole("button", { name: "Save", exact: true }).click();

		await expect(page.locator(".modal-dialog:visible")).toHaveCount(0);

		await page.reload();
		await desk.ready();

		await expect
			.poll(async () => Math.abs((await get_column_width(page, "module")) - 180))
			.toBeLessThanOrEqual(15);
	});

	test("drag-to-resize changes the column width and persists it", async ({ page, desk }) => {
		// BASE_FIELDS seeds module at 150 px, so 150+60=210 — well inside the 400 px cap.
		const initial_width = await get_column_width(page, "module");
		await drag_resize_column(page, "module", 60);
		await expect
			.poll(() => get_column_width(page, "module"))
			.toBeGreaterThan(initial_width + 30);

		await page.reload();
		await desk.ready();

		await expect
			.poll(() => get_column_width(page, "module"))
			.toBeGreaterThan(initial_width + 30);
	});

	test("enforces minimum column width of 50 px when dragging", async ({ page }) => {
		await drag_resize_column(page, "module", -2000);
		await expect.poll(() => get_column_width(page, "module")).toBeGreaterThanOrEqual(50);
	});

	test("enforces maximum column width of 400 px when dragging", async ({ page }) => {
		await drag_resize_column(page, "module", 2000);
		await expect.poll(() => get_column_width(page, "module")).toBeLessThanOrEqual(400);
	});
});

test.describe("List View — Column resize handle without System Manager", () => {
	const test_user = "test_list_col_width@example.com";
	const own_layout = "_test_layout_col_width_own";
	const global_layout = "_test_layout_col_width_global";
	const HANDLE = ".list-row-head .list-col-resize-handle";
	const VIEW_SWITCHER = ".custom-btn-group.view-switcher button:visible";
	const layout_columns = JSON.stringify([
		{ fieldname: "description", label: "Description" },
		{ fieldname: "priority", label: "Priority", width: 150 },
	]);
	let todo;

	async function select_layout(page, label) {
		await page.locator(VIEW_SWITCHER).click();
		await page.locator(".es-menu__item", { hasText: "List View" }).first().hover();
		await page.locator(".es-menu__item", { hasText: label }).first().click();
		await expect(page.locator(VIEW_SWITCHER)).toContainText(label);
		await expect(page.locator('.list-row-head [data-fieldname="date"]')).toHaveCount(0);
		await expect(page.locator('.list-row-head [data-fieldname="priority"]')).toBeVisible();
	}

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: test_user,
			role: "System Manager",
		});
		todo = await admin.insert_doc("ToDo", {
			description: "Column resize handle test",
			allocated_to: test_user,
		});
		await admin.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", {
			filter_name: own_layout,
			for_user: test_user,
			columns: layout_columns,
		});
		await admin.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", {
			filter_name: global_layout,
			for_user: "",
			columns: layout_columns,
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
		await admin.remove_doc("ToDo", todo.name, true);
	});

	test.beforeEach(async ({ page, desk, api }) => {
		await desk.login(test_user);
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
		await page.goto("/desk/todo/view/list");
		await desk.ready();
		await expect(page.locator(".list-row-head")).toBeVisible();
	});

	test("hides the handle on the default layout", async ({ page }) => {
		await expect(page.locator(HANDLE)).toHaveCount(0);
	});

	test("hides the handle on a layout the user cannot edit", async ({ page }) => {
		await select_layout(page, global_layout);
		await expect(page.locator(HANDLE)).toHaveCount(0);
	});

	test("shows the handle on the user's own layout", async ({ page }) => {
		await select_layout(page, own_layout);
		await expect(page.locator(HANDLE).first()).toBeAttached();
	});
});

test.describe("List View — Column resize handle for System Manager", () => {
	test("shows the handle on the default layout", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
		await page.goto("/desk/todo/view/list");
		await desk.ready();
		await expect(
			page.locator(".list-row-head .list-col-resize-handle").first()
		).toBeAttached();
	});
});
