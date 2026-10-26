import { test, expect } from "../support";

test.describe("Dashboard Chart", () => {
	test("Check filter populate for child table doctype", async ({ page, desk }) => {
		await desk.new_form("Dashboard Chart");
		await expect(
			page.locator('.frappe-control[data-fieldname="parent_document_type"]')
		).toHaveCSS("display", "none");

		await desk.fill_field("document_type", "Workspace Link", "Link");
		await expect(desk.get_field("document_type", "Link")).toHaveValue("Workspace Link");

		await desk.fill_field("chart_name", "Test Chart", "Data");

		await page.locator('[data-fieldname="filters_json"]').click();
		await expect(page.locator(".modal-dialog")).toBeVisible();

		await page.locator(".modal-body .filter-action-buttons .add-filter").click();
		await page.locator(".modal-body .fieldname-select-area").click();
		await page.locator(".modal-actions .btn-modal-close").click();
	});
});
