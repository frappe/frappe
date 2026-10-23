import { test, expect } from "../support";

const CHART = "TEST-CHART-RENDERER";
const DASHBOARD = "TEST-CHART-RENDERER-DASHBOARD";
const REPORT = "Test Chart Renderer Report";
const MARKER = "chart renderer test";

const set_classic_charts = (admin, value) =>
	admin.set_value("System Settings", "System Settings", { use_classic_charts: value });

async function open_dashboard_chart(page) {
	await page.goto(`/desk/dashboard-view/${DASHBOARD}`);
	return page.locator(".dashboard-widget-box").filter({ hasText: CHART });
}

async function open_report_chart(page) {
	await page.goto(`/desk/query-report/${REPORT}`);
	return page.locator("#page-query-report .chart-wrapper");
}

async function expect_island(container) {
	await expect(container.locator(".frappe-island").locator("canvas, svg").first()).toBeVisible();
	await expect(container.locator("svg.frappe-chart")).toHaveCount(0);
}

async function expect_frappe_charts(container) {
	await expect(container.locator("svg.frappe-chart")).toBeVisible();
	await expect(container.locator(".frappe-island")).toHaveCount(0);
}

test.describe("Desk charts", () => {
	let original;

	test.beforeAll(async ({ admin }) => {
		original = (await admin.get_doc("System Settings", "System Settings")).data
			.use_classic_charts;

		await admin.create_records({ doctype: "ToDo", description: MARKER });

		await admin.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: CHART,
				chart_type: "Group By",
				document_type: "ToDo",
				group_by_based_on: "status",
				group_by_type: "Count",
				type: "Bar",
				timeseries: 0,
				filters_json: JSON.stringify([["ToDo", "description", "like", `%${MARKER}%`]]),
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

		await admin.insert_doc(
			"Report",
			{
				report_name: REPORT,
				ref_doctype: "ToDo",
				report_type: "Query Report",
				is_standard: "No",
				query: "select name, description from tabToDo",
				javascript: `frappe.query_reports[${JSON.stringify(REPORT)}] = {
					get_chart_data: () => ({
						type: "bar",
						data: { labels: ["Open", "Closed"], datasets: [{ values: [3, 5] }] },
					}),
				};`,
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await set_classic_charts(admin, original || 0);
	});

	test("draws in the frappe.chart island", async ({ page, admin }) => {
		await set_classic_charts(admin, 0);

		await expect_island(await open_dashboard_chart(page));
		await expect_island(await open_report_chart(page));
	});

	test("draws with frappe-charts under Use Classic Charts", async ({ page, admin }) => {
		await set_classic_charts(admin, 1);

		await expect_frappe_charts(await open_dashboard_chart(page));
		await expect_frappe_charts(await open_report_chart(page));
	});

	test("the old chart APIs warn once, frappe.ui.chart never", async ({ page, admin, desk }) => {
		await set_classic_charts(admin, 1);
		await page.goto("/desk/todo");
		await desk.ready();

		const result = await page.evaluate(() => {
			const warn = console.warn;
			const warnings = [];
			console.warn = (message) => warnings.push(message);

			const config = () => ({
				type: "bar",
				data: { labels: ["Open", "Closed"], datasets: [{ values: [3, 5] }] },
			});
			const draw = (make) => {
				const el = document.createElement("div");
				document.body.append(el);
				return make(el);
			};

			const result = {};
			try {
				result.is_classic = frappe.ui.chart.is_classic(config());
				draw((el) => frappe.ui.chart(el, config()));
				result.after_chart = [...warnings];

				draw((el) => new frappe.ui.RealtimeChart(el, "chart_test", 8, config()));
				result.after_realtime = [...warnings];

				const charts = [1, 2].map(() => draw((el) => new frappe.Chart(el, config())));
				result.draws_frappe_charts = charts.every((chart) => chart.addDataPoint);
				result.after_frappe_chart = [...warnings];
			} finally {
				console.warn = warn;
			}
			return result;
		});

		expect(result.is_classic).toBe(true);
		expect(result.after_chart).toEqual([]);
		expect(result.after_realtime).toEqual([
			"frappe.ui.RealtimeChart is deprecated, call frappe.ui.chart and update(data) with the growing data object",
		]);
		expect(result.draws_frappe_charts).toBe(true);
		expect(result.after_frappe_chart).toEqual([
			...result.after_realtime,
			"frappe.Chart is deprecated, use frappe.ui.chart",
		]);
	});
});
