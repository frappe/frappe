import { test, expect } from "../support";

test.describe("Number Card", () => {
	test("Check filter populate for child table doctype", async ({ page, desk }) => {
		await desk.new_form("Number Card");
		await expect(
			page.locator('.frappe-control[data-fieldname="parent_document_type"]')
		).toHaveCSS("display", "none");

		await desk.fill_field("document_type", "Workspace Link", "Link");
		await expect(desk.get_field("document_type", "Link")).toHaveValue("Workspace Link");

		await desk.fill_field("label", "Test Number Card", "Data");
		await expect(desk.get_field("parent_document_type", "Link")).toHaveValue("Workspace");

		await page.locator('[data-fieldname="filters_json"]').click();
		await page.locator(".modal-body .filter-action-buttons .add-filter").click();
		await page.locator(".modal-body .fieldname-select-area").click();
		await page.locator(".modal-actions .btn-modal-close").click();
	});
});
