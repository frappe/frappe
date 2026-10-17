import { test, expect } from "../support";

const DOCTYPE = "DocType";
const LIST_URL = "/desk/List/DocType/List";
const SAVE_SETTINGS =
	"frappe.desk.doctype.list_view_settings.list_view_settings.save_listview_settings";
const SAVE_USER_SETTINGS = "frappe.model.utils.user_settings.save";

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

// Drags save widths per user, so each test starts from the site-wide widths.
function clear_user_column_widths(api, doctype) {
	return api.call(SAVE_USER_SETTINGS, { doctype, user_settings: { List: {} } });
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
	test.beforeEach(async ({ page, desk, api }) => {
		await save_list_view_settings(api, BASE_FIELDS);
		await clear_user_column_widths(api, DOCTYPE);
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

	test("drag-to-resize leaves the site-wide width unchanged", async ({ page, api }) => {
		await drag_resize_column(page, "module", 60);

		const { data } = await api.get_doc("List View Settings", DOCTYPE);
		const column = JSON.parse(data.fields).find((field) => field.fieldname === "module");
		expect(column.width).toBe(150);
	});

	test("Reset Column Widths goes back to the site-wide width", async ({ page, desk }) => {
		await drag_resize_column(page, "module", 60);
		await desk.click_menu_button("Reset Column Widths");
		await expect
			.poll(async () => Math.abs((await get_column_width(page, "module")) - 150))
			.toBeLessThanOrEqual(15);
		await expect(page.locator(".list-row-head .list-count")).not.toBeEmpty();

		await page.reload();
		await desk.ready();

		await expect
			.poll(async () => Math.abs((await get_column_width(page, "module")) - 150))
			.toBeLessThanOrEqual(15);
	});

	test("List Settings does not offer a dragged width as the site-wide one", async ({
		page,
		desk,
	}) => {
		await drag_resize_column(page, "name", 60);
		await open_list_settings(page, desk);

		await expect(
			page.locator('.modal-dialog:visible [data-fieldname="name"] input.form-control')
		).toHaveValue("");
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
