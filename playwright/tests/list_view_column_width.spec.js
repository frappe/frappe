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

	test("persists column width across page reloads", async ({ page, desk, api }) => {
		await save_list_view_settings(
			api,
			JSON.stringify([
				{ fieldname: "name", label: "Name" },
				{ fieldname: "module", label: "Module", width: 220 },
			])
		);

		await page.reload();
		await desk.ready();

		await expect
			.poll(async () => Math.abs((await get_column_width(page, "module")) - 220))
			.toBeLessThanOrEqual(15);
	});

	test("drag-to-resize handle changes column width", async ({ page }) => {
		// BASE_FIELDS seeds module at 150 px, so 150+80=230 — well inside the 400 px cap.
		const initial_width = await get_column_width(page, "module");
		await drag_resize_column(page, "module", 80);
		await expect
			.poll(() => get_column_width(page, "module"))
			.toBeGreaterThan(initial_width + 40);
	});

	test("drag-to-resize width is persisted in List View Settings", async ({ page, desk }) => {
		// BASE_FIELDS seeds module at 150 px, so 150+60=210 — well inside the 400 px cap.
		const initial_width = await get_column_width(page, "module");
		await drag_resize_column(page, "module", 60);

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

	test("shows resize handles in the list header", async ({ page }) => {
		await expect(page.locator(".list-row-head .list-col-resize-handle")).not.toHaveCount(0);
	});

	test("shows Width (px) column header and drag hint in List View Settings", async ({
		page,
		desk,
	}) => {
		await open_list_settings(page, desk);

		const dialog = page.locator(".modal-dialog:visible");
		await expect(dialog).toContainText("Width (px)");
		const hint_count = await dialog
			.locator("[title]")
			.evaluateAll(
				(elements) =>
					elements.filter((el) => el.title.toLowerCase().includes("drag")).length
			);
		expect(hint_count).toBeGreaterThan(0);

		await dialog.locator(".btn-modal-close").click();
	});
});
