import { test, expect } from "../support";

test.describe("Grid Configuration", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/app/doctype/User");
	});

	test.afterEach(async ({ api }) => {
		await api.call("frappe.model.utils.user_settings.save", {
			doctype: "DocType",
			user_settings: JSON.stringify({ GridView: null }),
		});
	});

	test("Set user wise grid settings", async ({ page }) => {
		await page.getByRole("tab", { name: "Settings", exact: true }).click();
		await page.locator('.form-section[data-fieldname="fields_section"]').click();
		const table = page.locator('.frappe-control[data-fieldname="fields"]');
		await table.locator(".icon-sm").click();
		const modal = page.locator('.frappe-control[data-fieldname="fields_html"]');
		await modal.locator(".add-new-fields").click();
		await page.locator('[type="checkbox"][data-unit="read_only"]').check();
		await page.getByRole("button", { name: "Add", exact: true }).click();
		const column_width = page.locator('.form-control.column-width[data-fieldname="options"]');
		await column_width.fill("1");
		await column_width.dispatchEvent("change");
		await page.getByRole("button", { name: "Update", exact: true }).click();
		await expect(page.locator('[title="Read Only"]').first()).toBeVisible();
	});
});
