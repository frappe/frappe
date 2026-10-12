import { test, expect, TEST_USER } from "../support";

test.describe("frappe.db.get_list", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/todo");
		await desk.ready();
	});

	test("loads with a filter too long for a URL", async ({ page }) => {
		const names = await page.evaluate(async (user) => {
			const missing = Array.from({ length: 3000 }, (_, i) => `missing-${i}@example.com`);
			const rows = await frappe.db.get_list("User", {
				filters: { name: ["in", [user, ...missing]] },
				limit: 0,
			});
			return rows.map((row) => row.name);
		}, TEST_USER);

		expect(names).toEqual([TEST_USER]);
	});

	test("rejects when the request fails", async ({ page }) => {
		await page.route("**/api/method/frappe.desk.reportview.get_list**", (route) =>
			route.fulfill({ status: 414, body: "" })
		);

		const rejected = await page.evaluate(() =>
			frappe.db.get_list("User").then(
				() => false,
				() => true
			)
		);

		expect(rejected).toBe(true);
	});
});
