import { test, expect } from "../support";

test.describe("Dashboard Chart Legend", () => {
	const chart_name = "TEST-LEGEND-TRUNCATION";
	const dashboard_name = "TEST-LEGEND-DASHBOARD";
	const marker = "legend truncation test";

	// DocType names longer than the 18 character legend cap
	const long_labels = [
		"Dashboard Chart Source",
		"Document Naming Rule",
		"Workspace Sidebar Item",
	];

	test.beforeAll(async ({ admin }) => {
		await admin.create_records(
			long_labels.map((reference_type) => ({
				doctype: "ToDo",
				description: `${marker} ${reference_type}`,
				reference_type: reference_type,
			}))
		);

		await admin.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: chart_name,
				chart_type: "Group By",
				document_type: "ToDo",
				group_by_based_on: "reference_type",
				group_by_type: "Count",
				type: "Percentage",
				timeseries: 0,
				filters_json: JSON.stringify([["ToDo", "description", "like", `%${marker}%`]]),
			},
			true
		);

		await admin.insert_doc(
			"Dashboard",
			{
				name: dashboard_name,
				dashboard_name: dashboard_name,
				is_standard: 0,
				charts: [{ chart: chart_name }],
			},
			true
		);
	});

	test("keeps long legend labels truncated when a circular chart is re-rendered", async ({
		page,
	}) => {
		await page.goto(`/desk/dashboard-view/${dashboard_name}`);

		await expect(page.locator(".chart-legend .legend-dataset-label").first()).toContainText(
			"..."
		);

		await page
			.locator(".chart-legend")
			.evaluate((legend) => legend.setAttribute("data-first-render", "1"));

		// the path every chart filter and timespan handler goes through
		const widget = await page.evaluate((chart_name) => {
			const widget = frappe.dashboard.chart_group.widgets_list.find(
				(w) => w.chart_doc && w.chart_doc.chart_name === chart_name
			);
			const state = { found: Boolean(widget), rendered: Boolean(widget?.dashboard_chart) };
			widget?.fetch_and_update_chart();
			return state;
		}, chart_name);
		expect(widget.found, "chart widget was found on the page").toBe(true);
		expect(widget.rendered, "chart was already rendered once").toBe(true);

		await expect(
			page
				.locator(".chart-legend:not([data-first-render])")
				.locator(".legend-dataset-label")
				.first()
		).toContainText("...");
	});
});
