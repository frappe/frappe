import { test, expect } from "../support";

test.describe("Dashboard Chart", () => {
	test("Check filter populate for child table doctype", async ({ page, desk }) => {
		await desk.new_form("Dashboard Chart");
		await expect(
			page.locator('.frappe-control[data-fieldname="parent_document_type"]')
		).toHaveCSS("display", "none");

		await expect(desk.get_field("chart_name", "Data")).toBeVisible();
		await desk.fill_field("chart_name", "Test Chart", "Data");
		await desk.fill_field("document_type", "Workspace Link", "Link");
		await expect(desk.get_field("parent_document_type", "Link")).toHaveValue("Workspace");

		await page.locator('[data-fieldname="filters_json"]').click();
		await expect(page.locator(".modal-dialog")).toBeVisible();

		await page.locator(".modal-body .filter-action-buttons .add-filter").click();
		await page.locator(".modal-body .fieldname-select-area").click();
		await page.locator(".modal-actions .btn-modal-close").click();
	});
});

test.describe("Dashboard Chart custom options", () => {
	const CHART = "TEST-CUSTOM-OPTIONS";
	const DASHBOARD = "TEST-CUSTOM-OPTIONS-DASHBOARD";

	test.beforeAll(async ({ admin }) => {
		await admin.create_records({ doctype: "ToDo", description: "custom options" });
		await admin.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: CHART,
				chart_type: "Count",
				document_type: "ToDo",
				based_on: "creation",
				filters_json: "[]",
				custom_options: '{"__proto__": {"valuesOverPoints": 1}}',
			},
			true
		);
		await admin.insert_doc(
			"Dashboard",
			{
				name: DASHBOARD,
				dashboard_name: DASHBOARD,
				is_standard: 0,
				charts: [{ chart: CHART }],
			},
			true
		);
	});

	test("custom options leave other objects untouched", async ({ page }) => {
		await page.goto(`/desk/dashboard-view/${DASHBOARD}`);
		await expect(
			page
				.locator(".dashboard-widget-box")
				.filter({ hasText: CHART })
				.locator(".frappe-island canvas, .frappe-island svg, svg.frappe-chart")
				.first()
		).toBeVisible();

		expect(await page.evaluate(() => ({}.valuesOverPoints))).toBeUndefined();
	});
});
