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
<<<<<<< HEAD
=======

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
>>>>>>> 6961dd0 (test: dashboard chart custom options leave other objects untouched)
