import { test, expect } from "../support";
import child_table_with_tabs from "../fixtures/child_table_with_tabs";
import doctype_with_child_table_tabs from "../fixtures/doctype_with_child_table_tabs";

const parent_doctype_name = doctype_with_child_table_tabs.name;

test.describe("Grid Row Form Tabs", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", child_table_with_tabs, true);
		await admin.insert_doc("DocType", doctype_with_child_table_tabs, true);
	});

	const new_form_with_rows = async (page, desk, title, row_count = 1) => {
		await desk.new_form(parent_doctype_name);
		await desk.fill_field("title", title);

		const table = page.locator('.frappe-control[data-fieldname="items"]');
		for (let i = 0; i < row_count; i++) {
			await table.getByRole("button", { name: "Add row", exact: true }).click();
		}
		return table;
	};

	const open_row_form = async (page, table, idx = 1) => {
		await table.locator(`[data-idx="${idx}"] .btn-open-row`).click();
		const table_form = page.locator(".grid-row-open");
		// the row form focuses its first input once its opening animation is over
		await expect(table_form.locator(".form-area input").first()).toBeFocused();
		return table_form;
	};

	const open_tab = async (table_form, fieldname) => {
		const tab = table_form.locator(`.form-tabs .nav-link[data-fieldname="${fieldname}"]`);
		await tab.click();
		await expect(tab).toHaveClass(/(^|\s)active(\s|$)/);
	};

	test("should display tabs in grid row form", async ({ page, desk }) => {
		const table = await new_form_with_rows(page, desk, "Test Document");
		const table_form = await open_row_form(page, table);

		await expect(table_form.locator(".form-tabs-list")).toBeVisible();
		await expect(table_form.locator(".form-tabs .nav-item")).toHaveCount(2);

		await expect(table_form.locator(".form-tabs .nav-link").first()).toHaveClass(
			/(^|\s)active(\s|$)/
		);
	});

	test("should switch tabs in grid row form", async ({ page, desk }) => {
		const table = await new_form_with_rows(page, desk, "Test Tab Switch");
		const table_form = await open_row_form(page, table);

		await expect(
			table_form.locator('.frappe-control[data-fieldname="item_name"]')
		).toBeVisible();
		await expect(
			table_form.locator('.frappe-control[data-fieldname="quantity"]')
		).toBeVisible();

		await open_tab(table_form, "tab_details");

		await expect(table_form.locator(".form-tabs .nav-link").first()).not.toHaveClass(
			/(^|\s)active(\s|$)/
		);

		await expect(
			table_form.locator('.frappe-control[data-fieldname="description"]')
		).toBeVisible();
		await expect(table_form.locator('.frappe-control[data-fieldname="notes"]')).toBeVisible();
	});

	test("should preserve tab state when switching between rows", async ({ page, desk }) => {
		const table = await new_form_with_rows(page, desk, "Test Tab Persistence", 2);

		const table_form = await open_row_form(page, table);
		await open_tab(table_form, "tab_details");

		await table_form.locator(".grid-collapse-row").click();

		const table_form2 = await open_row_form(page, table, 2);

		await expect(table_form2.locator(".form-tabs .nav-link").first()).toHaveClass(
			/(^|\s)active(\s|$)/
		);
	});

	test("should jump to a field inside the grid row form", async ({ page, desk }) => {
		const table = await new_form_with_rows(page, desk, "Test Jump To Field");
		const table_form = await open_row_form(page, table);

		// a real Escape keypress closes the open row form, so drop focus without it
		await page.locator(":focus").blur();
		await page.keyboard.press("Control+j");
		await page.locator(".modal input[type='text']").first().focus();
		await page.keyboard.type("Notes");
		await expect(
			page.locator(".modal:visible [role='listbox'] li", { hasText: "Notes" }).first()
		).toBeVisible();
		await page.keyboard.press("Enter");
		await expect
			.poll(() => page.evaluate(() => cur_dialog.get_value("fieldname")))
			.toBe("notes");
		await page.getByRole("button", { name: "Go", exact: true }).click();

		await expect(page.locator(".grid-row-open")).toBeAttached();
		await expect(
			table_form.locator('.frappe-control[data-fieldname="notes"] input')
		).toBeFocused();
	});

	test("should allow data entry in fields across different tabs", async ({ page, desk }) => {
		const table = await new_form_with_rows(page, desk, "Test Data Entry");
		const table_form = await open_row_form(page, table);

		await desk.fill_table_field("items", "1", "item_name", "Test Item");
		await desk.fill_table_field("items", "1", "quantity", "10");

		await open_tab(table_form, "tab_details");

		await expect(
			table_form.locator('.frappe-control[data-fieldname="description"]')
		).toBeVisible();
		await desk.fill_table_field("items", "1", "description", "This is a test description");
		await desk.fill_table_field("items", "1", "notes", "Some notes here");

		await open_tab(table_form, "tab_general");
		await expect(
			table_form.locator('.frappe-control[data-fieldname="item_name"] input')
		).toHaveValue("Test Item");
	});
});
