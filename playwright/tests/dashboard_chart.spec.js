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

test.describe("Dashboard Chart heatmap", () => {
	const CHART = "TEST-HEATMAP-YEAR";
	const DASHBOARD = "TEST-HEATMAP-YEAR-DASHBOARD";
	let original_classic_charts;

	test.beforeAll(async ({ admin }) => {
		// the months counted below are frappe-charts markup
		original_classic_charts = (await admin.get_doc("System Settings", "System Settings")).data
			.use_classic_charts;
		await admin.set_value("System Settings", "System Settings", { use_classic_charts: 1 });

		await admin.create_records({ doctype: "ToDo", description: "heatmap year" });
		await admin.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: CHART,
				chart_type: "Count",
				document_type: "ToDo",
				based_on: "creation",
				type: "Heatmap",
				heatmap_year: String(new Date().getFullYear()),
				filters_json: JSON.stringify([["ToDo", "description", "=", "heatmap year"]]),
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

	test.afterAll(async ({ admin }) => {
		await admin.set_value("System Settings", "System Settings", {
			use_classic_charts: original_classic_charts || 0,
		});
	});

	test("draws the year as twelve months", async ({ page }) => {
		await page.goto(`/desk/dashboard-view/${DASHBOARD}`);
		const chart = page
			.locator(".dashboard-widget-box")
			.filter({ hasText: CHART })
			.locator("svg.frappe-chart");

		await expect(chart).toBeVisible();
		await expect(chart.locator(".heat-domain")).toHaveCount(12);
	});
});
