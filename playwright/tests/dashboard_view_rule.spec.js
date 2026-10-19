import { test, expect } from "../support";

// The server's `__onload` is faked, so the page rule runs on a site without the app that claims.
const DASHBOARD = "TODO-VIEW-RULE-DASHBOARD";
const ISLAND = { name: "someapp.dashboard", props: { dashboard: "sales" } };

const cases = [
	{
		title: "without Insights, classic with the install prompt",
		onload: { dashboards: "Insights", show_insights_dashboards_prompt: true },
		view: "classic",
		prompt: "Insights dashboards are available for this site",
		button: "Install Insights",
	},
	{
		title: "Insights claims it on a Classic site, classic with the open prompt",
		onload: {
			island: ISLAND,
			dashboards: "Classic",
			show_insights_dashboards_prompt: true,
			insights_dashboard_title: "Sales Overview",
		},
		view: "classic",
		prompt: "This dashboard has an Insights version: Sales Overview",
		button: "Open",
	},
	{
		title: "Insights claims it on an Insights site, the island",
		onload: { island: ISLAND, dashboards: "Insights", show_insights_dashboards_prompt: true },
		view: "island",
	},
	{
		title: "Insights is installed and does not claim it, classic with no prompt",
		onload: { dashboards: "Insights" },
		view: "classic",
	},
	{
		title: "an app claims a dashboard with no Insights version, the island",
		onload: { island: ISLAND },
		view: "island",
	},
];

test.describe("Dashboard view rule", () => {
	test.beforeEach(async ({ page, desk, api }) => {
		await page.goto("/desk");
		await desk.ready();
		await api.insert_doc(
			"Dashboard",
			{ name: DASHBOARD, dashboard_name: DASHBOARD, is_standard: 0 },
			true
		);
	});

	for (const { title, onload, view, prompt, button } of cases) {
		test(title, async ({ page }) => {
			await page.route("**/api/method/frappe.desk.form.load.getdoc?*", async (route) => {
				const response = await route.fetch();
				const json = await response.json();
				json.docs[0].__onload = onload;
				await route.fulfill({ response, json });
			});

			await page.goto(`/desk/dashboard-view/${DASHBOARD}`);

			const island = page.locator(".dashboard-view-island");
			const classic = page.locator(".dashboard-graph");
			await expect(view === "island" ? island : classic).toBeAttached();
			await expect(view === "island" ? classic : island).toHaveCount(0);

			const banner = page.locator(".dashboard-view-prompt");
			if (prompt) {
				await expect(banner).toContainText(prompt);
				await expect(banner.getByRole("button", { name: button })).toBeVisible();
			} else {
				await expect(banner).toHaveCount(0);
			}
		});
	}
});
