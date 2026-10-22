import { test, expect } from "../support";

const DOCTYPE = "ToDo";
const LIST_URL = "/desk/List/ToDo/List";
const SAVE_USER_SETTINGS = "frappe.model.utils.user_settings.save";
// set as the Priority width in Customize Form, so drag tests have a predictable baseline
const DEFAULT_WIDTH = 150;

async function open_list_settings(page, desk) {
	await desk.click_menu_button("List Settings");
	await expect(page.locator(".modal-dialog:visible")).toContainText(
		`${DOCTYPE} List View Settings`
	);
}

// Drags save widths per user, so each test starts from the site-wide widths.
function clear_user_column_widths(api, doctype) {
	return api.call(SAVE_USER_SETTINGS, { doctype, user_settings: { List: {} } });
}

function get_column_width(page, fieldname) {
	return page
		.locator(`.list-row-head .list-row-col[data-fieldname="${fieldname}"]`)
		.evaluate((el) => $(el).outerWidth());
}

async function get_saved_width(api, fieldname) {
	const { message } = await api.call("frappe.client.get_value", {
		doctype: "List View Settings",
		filters: { name: DOCTYPE },
		fieldname: "fields",
	});
	return JSON.parse(message?.fields || "[]").find((field) => field.fieldname === fieldname)
		?.width;
}

function width_input(page, fieldname) {
	return page.locator(
		`.modal-dialog:visible [data-fieldname="${fieldname}"] input.form-control`
	);
}

async function save_list_settings(page) {
	await page.getByRole("button", { name: "Save", exact: true }).click();
	await expect(page.locator(".modal-dialog:visible")).toHaveCount(0);
}

const within = (expected) => (width) => Math.abs(width - expected) <= 15;

// Simulate drag-to-resize using jQuery $.Event so that both the delegated
// mousedown handler on $result and the document-level mousemove/mouseup
// handlers receive events with the right pageX values. Dropping the handle
// saves the new width, so wait for that save to land.
async function drag_resize_column(page, fieldname, delta_x) {
	const width_saved = page.waitForResponse(
		(res) =>
			res.url().includes(SAVE_USER_SETTINGS) &&
			res.request().postData()?.includes("column_widths")
	);
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
	await width_saved;
}

test.describe("List View — Column Widths", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Property Setter",
			{
				doctype_or_field: "DocField",
				doc_type: DOCTYPE,
				field_name: "priority",
				property: "width",
				property_type: "Data",
				value: String(DEFAULT_WIDTH),
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Property Setter", `${DOCTYPE}-priority-width`, true);
		await admin.remove_doc("List View Settings", DOCTYPE, true);
	});

	test.beforeEach(async ({ page, desk, api }) => {
		await clear_user_column_widths(api, DOCTYPE);
		await page.goto(LIST_URL);
		await desk.ready();
		await desk.clear_filters();
	});

	test("saves the width typed in List Settings only for the user", async ({
		page,
		desk,
		api,
	}) => {
		await open_list_settings(page, desk);
		await expect(width_input(page, "priority")).toHaveValue(String(DEFAULT_WIDTH));
		await width_input(page, "priority").fill("180");
		await save_list_settings(page);

		await expect.poll(() => get_column_width(page, "priority").then(within(180))).toBe(true);
		expect(await get_saved_width(api, "priority")).toBeUndefined();

		await page.reload();
		await desk.ready();

		await expect.poll(() => get_column_width(page, "priority").then(within(180))).toBe(true);
	});

	test("a smaller width from List Settings shows without a reload", async ({ page, desk }) => {
		await open_list_settings(page, desk);
		await width_input(page, "priority").fill("90");
		await save_list_settings(page);

		await expect.poll(() => get_column_width(page, "priority").then(within(90))).toBe(true);
	});

	test("drag-to-resize changes the column width and persists it", async ({ page, desk }) => {
		// 150+60=210 — well inside the 400 px cap.
		const initial_width = await get_column_width(page, "priority");
		await drag_resize_column(page, "priority", 60);
		await expect
			.poll(() => get_column_width(page, "priority"))
			.toBeGreaterThan(initial_width + 30);

		await page.reload();
		await desk.ready();

		await expect
			.poll(() => get_column_width(page, "priority"))
			.toBeGreaterThan(initial_width + 30);
	});

	test("enforces minimum column width of 50 px when dragging", async ({ page }) => {
		await drag_resize_column(page, "priority", -2000);
		await expect.poll(() => get_column_width(page, "priority")).toBeGreaterThanOrEqual(50);
	});

	test("enforces maximum column width of 400 px when dragging", async ({ page }) => {
		await drag_resize_column(page, "priority", 2000);
		await expect.poll(() => get_column_width(page, "priority")).toBeLessThanOrEqual(400);
	});

	test("drag-to-resize leaves List View Settings unchanged", async ({ page, api }) => {
		await drag_resize_column(page, "priority", 60);

		expect(await get_saved_width(api, "priority")).toBeUndefined();
	});

	test("Reset Column Widths goes back to the Customize Form width", async ({ page, desk }) => {
		await drag_resize_column(page, "priority", 60);
		await desk.click_menu_button("Reset Column Widths");
		await expect
			.poll(() => get_column_width(page, "priority").then(within(DEFAULT_WIDTH)))
			.toBe(true);
		await expect(page.locator(".list-row-head .list-count")).not.toBeEmpty();

		await page.reload();
		await desk.ready();

		await expect
			.poll(() => get_column_width(page, "priority").then(within(DEFAULT_WIDTH)))
			.toBe(true);
	});

	test("List Settings shows the width the user dragged to", async ({ page, desk }) => {
		await drag_resize_column(page, "priority", 60);
		const dragged_width = await get_column_width(page, "priority");
		await open_list_settings(page, desk);

		expect(
			within(dragged_width)(Number(await width_input(page, "priority").inputValue()))
		).toBe(true);
	});

	test("Create Layout starts from the width the user dragged to", async ({ page }) => {
		await drag_resize_column(page, "priority", 60);
		const dragged_width = await get_column_width(page, "priority");

		await page.locator(".custom-btn-group.view-switcher button:visible").click();
		await page.locator(".es-menu__item", { hasText: "List View" }).first().hover();
		await page.locator(".es-menu__item", { hasText: "Create Layout" }).first().click();

		const layout_width_input = page.locator(
			'.modal-dialog:visible .layout-column-width[data-fieldname="priority"]'
		);
		expect(within(dragged_width)(Number(await layout_width_input.inputValue()))).toBe(true);
	});
});

test.describe("List View — Column Widths on a saved layout", () => {
	const layout_name = "_test_layout_widths";

	test.beforeEach(async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.clear_list_layout_test_layouts");
		await api.call("frappe.tests.ui_test_helpers.reset_list_layout_test_user_settings");
		await clear_user_column_widths(api, "ToDo");
		await api.call("frappe.tests.ui_test_helpers.create_list_layout_test_layout", {
			layout_name,
			for_user: "",
			filters: "[]",
			columns: JSON.stringify([
				{ fieldname: "status", label: "Status", width: 100 },
				{ fieldname: "priority", label: "Priority", width: 120 },
				{ fieldname: "date", label: "Due Date" },
			]),
		});

		await page.goto("/desk/todo");
		await desk.ready();
		await page.locator(".custom-btn-group.view-switcher button:visible").click();
		await page.locator(".es-menu__item", { hasText: "List View" }).first().hover();
		await page.locator(".es-menu__item", { hasText: layout_name }).first().click();
		await expect.poll(() => get_column_width(page, "priority").then(within(120))).toBe(true);
	});

	async function get_layout_width(api, fieldname) {
		const { message } = await api.call("frappe.client.get_value", {
			doctype: "List Filter",
			filters: { filter_name: layout_name },
			fieldname: "columns",
		});
		return JSON.parse(message.columns).find((col) => col.fieldname === fieldname).width;
	}

	async function open_edit_layout(page) {
		await page.locator(".custom-btn-group.view-switcher button:visible").click();
		await page.locator(".es-menu__item", { hasText: "List View" }).first().hover();
		await page.locator(".es-menu__item", { hasText: "Manage Layouts" }).first().click();
		await page
			.locator(".layout-manage-row", { hasText: layout_name })
			.locator(".layout-action-edit")
			.click();
	}

	test("dragging on a global layout saves the width only for the user", async ({
		page,
		desk,
		api,
	}) => {
		await drag_resize_column(page, "priority", 60);

		expect(await get_layout_width(api, "priority")).toBe(120);

		await page.reload();
		await desk.ready();

		await expect.poll(() => get_column_width(page, "priority").then(within(180))).toBe(true);
	});

	test("Reset Column Widths goes back to the layout's width", async ({ page, desk }) => {
		await drag_resize_column(page, "priority", 60);
		await desk.click_menu_button("Reset Column Widths");

		await expect.poll(() => get_column_width(page, "priority").then(within(120))).toBe(true);
	});

	test("List Settings on a layout saves the width only for the user", async ({
		page,
		desk,
		api,
	}) => {
		await drag_resize_column(page, "status", 40);
		const dragged_status_width = await get_column_width(page, "status");

		await open_list_settings(page, desk);
		await expect(width_input(page, "priority")).toHaveValue("120");
		await width_input(page, "priority").fill("180");
		await save_list_settings(page);

		expect(await get_layout_width(api, "priority")).toBe(120);
		await expect.poll(() => get_column_width(page, "priority").then(within(180))).toBe(true);
		await expect
			.poll(() => get_column_width(page, "status").then(within(dragged_status_width)))
			.toBe(true);
	});

	test("Edit Layout does not save the user's width into a column without one", async ({
		page,
		api,
	}) => {
		await drag_resize_column(page, "date", 150);

		await open_edit_layout(page);
		await expect(
			page.locator('.modal-dialog:visible .layout-column-width[data-fieldname="date"]')
		).toHaveValue("200");
		await page.getByRole("button", { name: "Update", exact: true }).click();

		await expect.poll(() => get_layout_width(api, "date")).toBe(200);
	});

	test("Edit Layout starts from the layout's widths and keeps the user's other widths", async ({
		page,
		desk,
		api,
	}) => {
		await drag_resize_column(page, "status", 40);
		await drag_resize_column(page, "priority", 60);

		await open_edit_layout(page);

		const layout_width_input = page.locator(
			'.modal-dialog:visible .layout-column-width[data-fieldname="priority"]'
		);
		await expect(layout_width_input).toHaveValue("120");
		await layout_width_input.fill("200");
		await page.getByRole("button", { name: "Update", exact: true }).click();

		await expect.poll(() => get_layout_width(api, "priority")).toBe(200);
		await expect
			.poll(() => page.evaluate(() => Object.keys(cur_list.get_user_column_widths())))
			.toEqual(["status"]);

		await page.reload();
		await desk.ready();

		await expect.poll(() => get_column_width(page, "priority").then(within(200))).toBe(true);
	});
});

test.describe("List View — Column Widths without System Manager", () => {
	const test_user = "test_column_width@example.com";

	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_test_user", { username: test_user });
		await admin.call("frappe.tests.ui_test_helpers.add_remove_role", {
			action: "remove",
			user: test_user,
			role: "System Manager",
		});
		await admin.insert_doc("ToDo", {
			description: "Column width test",
			allocated_to: test_user,
		});
	});

	test.beforeEach(async ({ page, desk, api }) => {
		await desk.login(test_user);
		await clear_user_column_widths(api, "ToDo");
		await page.goto("/desk/List/ToDo/List");
		await desk.ready();
	});

	test("drag-to-resize saves the width for the user", async ({ page, desk }) => {
		const initial_width = await get_column_width(page, "priority");
		await drag_resize_column(page, "priority", 60);
		await expect(page.locator(".modal-dialog:visible")).toHaveCount(0);

		await page.reload();
		await desk.ready();

		await expect
			.poll(() => get_column_width(page, "priority"))
			.toBeGreaterThan(initial_width + 30);
	});
});
