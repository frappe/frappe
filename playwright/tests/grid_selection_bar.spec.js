import { test, expect } from "../support";

test.describe("Grid Selection Bar", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
	});

	test.beforeEach(async ({ page }) => {
		await page.goto("/desk/contact/Test Contact");
	});

	const get_table = (page) => page.locator('.frappe-control[data-fieldname="phone_nos"]');
	const get_bar = (page) => get_table(page).locator(".grid-selection-bar");
	const select_page = (page) =>
		get_table(page).locator(".grid-heading-row .grid-row-check").click();

	test("replaces the footer while rows are selected", async ({ page }) => {
		const table = get_table(page);
		const row_check = table.locator('.grid-row[data-idx="1"] .grid-row-check');

		await row_check.click();
		await expect(get_bar(page)).toContainText("1 row selected");
		await expect(table.locator(".grid-footer")).toBeHidden();

		await row_check.click();
		await expect(get_bar(page)).toBeHidden();
		await expect(table.locator(".grid-footer")).toBeVisible();
	});

	test("header checkbox selects only the current page", async ({ page }) => {
		const table = get_table(page);
		const bar = get_bar(page);

		await select_page(page);
		await expect(bar).toContainText("50 rows selected");

		await expect(bar.locator(".grid-selection-page")).toHaveText("1 of 20");
		await expect(bar.getByRole("button", { name: "Previous page" })).toBeDisabled();
		await bar.getByRole("button", { name: "Next page" }).click();
		await expect(bar.locator(".grid-selection-page")).toHaveText("2 of 20");
		await expect(table.locator(".grid-body .grid-row-check:checked")).toHaveCount(0);
		await expect(table.locator(".grid-heading-row .grid-row-check")).not.toBeChecked();
		await expect(bar).toContainText("50 rows selected");
	});

	test("select all selects rows on every page and clear resets", async ({ page }) => {
		const bar = get_bar(page);

		await select_page(page);
		await bar.getByRole("button", { name: "Select All" }).click();
		await expect(bar).toContainText("1000 rows selected");
		await expect(bar.getByRole("button", { name: "Select All" })).toBeDisabled();

		await bar.getByRole("button", { name: "Clear selection" }).click();
		await expect(bar).toBeHidden();
		await expect(get_table(page).locator(".grid-row-check:checked")).toHaveCount(0);
		await expect(get_table(page).locator(".grid-add-row")).toBeVisible();
	});

	test("asks before deleting selected rows", async ({ page }) => {
		const table = get_table(page);

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await table.locator('.grid-row[data-idx="2"] .grid-row-check').click();
		await get_bar(page).getByRole("button", { name: "Actions" }).click();
		await page.locator('.es-menu [role="menuitem"]', { hasText: "Delete" }).click();

		const dialog = page.locator(".modal-dialog:visible");
		await expect(dialog).toContainText("Are you sure you want to delete 2 rows?");
		await dialog.getByRole("button", { name: "Yes" }).click();

		await expect.poll(() => page.evaluate(() => cur_frm.doc.phone_nos.length)).toBe(998);
		await expect(get_bar(page)).toBeHidden();
	});

	test("scripts add custom actions and hide built-in ones", async ({ page }) => {
		const table = get_table(page);
		const menu_item = (label) =>
			page.locator('.es-menu [role="menuitem"]', { hasText: label });

		await page.waitForFunction(() => window.cur_frm?.get_field("phone_nos"));
		await page.evaluate(() => {
			const grid = cur_frm.get_field("phone_nos").grid;
			const mark_primary = {
				label: "Mark primary",
				icon: "star",
				action: (rows) => (window.marked_rows = rows.map((row) => row.idx)),
			};
			grid.add_bulk_action(mark_primary);
			grid.add_bulk_action(mark_primary);
			grid.toggle_bulk_action("delete", false);
		});

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await table.locator('.grid-row[data-idx="2"] .grid-row-check').click();
		await get_bar(page).getByRole("button", { name: "Actions" }).click();
		await expect(menu_item("Delete")).toHaveCount(0);
		await expect(menu_item("Mark primary")).toHaveCount(1);
		await menu_item("Mark primary").click();

		expect(await page.evaluate(() => window.marked_rows)).toEqual([1, 2]);
	});

	test("keeps footer custom buttons visible while rows are selected", async ({ page }) => {
		const table = get_table(page);
		const custom_button = table.getByRole("button", { name: "Verify numbers" });

		await page.waitForFunction(() => window.cur_frm?.get_field("phone_nos"));
		await page.evaluate(() =>
			cur_frm.get_field("phone_nos").grid.add_custom_button("Verify numbers", () => {})
		);

		await table.locator('.grid-row[data-idx="1"] .grid-row-check').click();
		await expect(get_bar(page)).toBeVisible();
		await expect(custom_button).toBeVisible();
		await expect(table.locator(".grid-add-row")).toBeHidden();

		await get_bar(page).getByRole("button", { name: "Actions" }).click();
		await expect(
			page.locator('.es-menu [role="menuitem"]', { hasText: "Verify numbers" })
		).toHaveCount(0);
	});
});
