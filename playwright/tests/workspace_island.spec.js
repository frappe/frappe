import { test, expect } from "../support";

const WORKSPACE = "Playwright Island";
const CARD = "Playwright ToDo Count";
const CHART = "Playwright ToDo Chart";
const SAVE_CHART_CONFIG = "dashboard_settings.save_chart_config";

test.describe("Workspace island", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc(
			"Number Card",
			{
				label: CARD,
				type: "Document Type",
				document_type: "ToDo",
				function: "Count",
				filters_json: "[]",
				is_public: 1,
			},
			true
		);
		await admin.insert_doc(
			"Dashboard Chart",
			{
				chart_name: CHART,
				chart_type: "Count",
				document_type: "ToDo",
				based_on: "creation",
				timeseries: 1,
				timespan: "Last Year",
				time_interval: "Monthly",
				type: "Bar",
				filters_json: "[]",
				is_public: 1,
			},
			true
		);
		await admin.insert_doc(
			"Workspace",
			{
				label: WORKSPACE,
				title: WORKSPACE,
				module: "Desk",
				public: 1,
				renderer: "Frappe UI",
				content: JSON.stringify([
					{ id: "pw-nc", type: "number_card", data: { number_card_name: CARD, col: 4 } },
					{ id: "pw-ch", type: "chart", data: { chart_name: CHART, col: 12 } },
				]),
				number_cards: [{ number_card_name: CARD, label: CARD }],
				charts: [{ chart_name: CHART, label: CHART }],
			},
			true
		);
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Workspace", WORKSPACE, true);
	});

	test("draws a Frappe UI workspace at its usual URL", async ({ page }) => {
		const errors = [];
		page.on("pageerror", (error) => errors.push(error.message));

		await page.goto("/desk/playwright-island");

		const tile = page.locator(".ws-tile", { hasText: CARD });
		await expect(tile).toBeVisible();
		await expect(tile).toContainText(/\d/);
		await expect(page).toHaveTitle(new RegExp(WORKSPACE));
		await expect(page).toHaveURL(/\/desk\/playwright-island$/);
		expect(errors).toEqual([]);
	});

	test("a chart keeps its timespan across a reload, and Refresh redraws it", async ({
		page,
		api,
	}) => {
		await page.goto("/desk/playwright-island");
		const tile = page.locator(".ws-tile", { hasText: CHART });
		await expect(tile.getByRole("button", { name: "Chart actions" })).toBeVisible();
		await page.evaluate(() => frappe.dashboard_utils.get_dashboard_settings());
		await api.call(`frappe.desk.doctype.dashboard_settings.${SAVE_CHART_CONFIG}`, {
			reset: 1,
			config: {},
			chart_name: CHART,
		});
		await page.reload();

		const saved = page.waitForResponse((res) => res.url().includes(SAVE_CHART_CONFIG));
		await tile.getByRole("button", { name: "Last Year" }).click();
		await page.getByRole("menuitem", { name: "Last Quarter" }).click();
		await saved;

		await page.reload();
		await expect(tile.getByRole("button", { name: "Last Quarter" })).toBeVisible();

		const refreshed = page.waitForResponse((res) => res.url().includes("dashboard_chart.get"));
		await tile.getByRole("button", { name: "Chart actions" }).click();
		await page.getByRole("menuitem", { name: "Refresh" }).click();
		await refreshed;
	});

	test("the workspace page has no URL of its own", async ({ page }) => {
		await page.goto("/desk/workspace-view/playwright-island");
		await expect(
			page.getByText("This workspace does not exist, or you cannot open it.")
		).toBeVisible();
	});
});
