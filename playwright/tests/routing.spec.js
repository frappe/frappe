const { test, expect } = require("@playwright/test");
const { login } = require("../utils");

const list_view = "/desk/todo";

// test round trip with filter types
const test_queries = [
	"?status=Open",
	`?date=%5B"Between"%2C%5B"2022-06-01"%2C"2022-06-30"%5D%5D`,
	`?date=%5B">"%2C"2022-06-01"%5D`,
	`?name=%5B"like"%2C"%2542%25"%5D`,
	`?status=%5B"not%20in"%2C%5B"Open"%2C"Closed"%5D%5D`,
	`?status=%5B%22%21%3D%22%2C%22Closed%22%5D&status=%5B%22%21%3D%22%2C%22Cancelled%22%5D`,
];

test.describe("SPA Routing", () => {
	test.beforeAll(async ({ browser }) => {
		const context = await browser.newContext();
		const page = await context.newPage();
		await login(page);
		await page.goto("/desk/todo");
		await context.close();
	});

	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test("should apply filter on list view from route", async ({ page }) => {
		for (const query of test_queries) {
			const full_url = `${list_view}${query}`;
			await page.goto(full_url);

			// Wait for the page title to be visible
			await expect(page.getByTitle("To Do")).toBeVisible({ timeout: 5000 });

			const expected = new URLSearchParams(query);
			const actual_url = new URL(page.url());
			const actual = new URLSearchParams(actual_url.search);

			// This might appear like a dumb test checking visited URL to itself
			// but it's actually doing a round trip
			// URL with params -> parsed filters -> new URL
			// if it's same that means everything worked in between.
			expect(actual.toString()).toBe(expected.toString());
		}
	});
});
