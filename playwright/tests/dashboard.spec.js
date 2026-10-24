import { test, expect } from "../support";

test.describe("Dashboard view", () => {
	test("should load", async ({ page, desk, api }) => {
		const chart = "TODO-YEARLY-TRENDS";
		const dashboard = "TODO-TEST-DASHBOARD";

		await page.goto("/desk");
		await desk.ready();

		await api.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: chart,
				chart_type: "Count",
				document_type: "ToDo",
				parent_document_type: "",
				based_on: "creation",
				group_by_type: "Count",
				timespan: "Last Year",
				time_interval: "Yearly",
				timeseries: 1,
				type: "Line",
				filters_json: "[]",
			},
			true
		);

		await api.insert_doc(
			"Dashboard",
			{
				name: dashboard,
				dashboard_name: dashboard,
				is_standard: 0,
				charts: [{ chart: chart }],
			},
			true
		);

		await page.goto(`/desk/dashboard-view/${dashboard}`);

		await expect(page.getByText(chart, { exact: true })).toBeVisible();
	});

	test("a dashboard the reader cannot open clears the one drawn before", async ({
		page,
		desk,
		api,
	}) => {
		const dashboard = "TODO-CLEAR-DASHBOARD";

		await page.goto("/desk");
		await desk.ready();
		await api.insert_doc(
			"Dashboard",
			{ name: dashboard, dashboard_name: dashboard, is_standard: 0 },
			true
		);
		await page.goto(`/desk/dashboard-view/${dashboard}`);
		await expect(page.locator(".dashboard-graph")).toBeAttached();

		await page.route("**/api/method/frappe.desk.form.load.getdoc?*", (route) =>
			route.fulfill({ status: 403, json: { exc_type: "PermissionError" } })
		);
		await page.evaluate(() => frappe.set_route("dashboard-view", "Not Permitted Dashboard"));

		await expect(page.locator(".dashboard-graph")).toHaveCount(0);
	});
});
