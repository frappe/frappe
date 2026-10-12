import { test, expect } from "../support";

const list_view = "/desk/todo";

const test_queries = [
	"?status=Open",
	`?date=%5B"Between"%2C%5B"2022-06-01"%2C"2022-06-30"%5D%5D`,
	`?date=%5B">"%2C"2022-06-01"%5D`,
	`?name=%5B"like"%2C"%2542%25"%5D`,
	`?status=%5B"not%20in"%2C%5B"Open"%2C"Closed"%5D%5D`,
	`?status=%5B%22%21%3D%22%2C%22Closed%22%5D&status=%5B%22%21%3D%22%2C%22Cancelled%22%5D`,
];

test.describe("SPA Routing", () => {
	test.afterEach(async ({ desk }) => {
		await desk.clear_filters();
	});

	test("should apply filter on list view from route", async ({ page }) => {
		for (const query of test_queries) {
			await page.goto(`${list_view}${query}`);
			await expect(page.getByTitle("To Do", { exact: true }).first()).toBeAttached();

			// A round trip: URL with params -> parsed filters -> new URL.
			const expected = new URLSearchParams(query);
			await expect
				.poll(() => new URLSearchParams(new URL(page.url()).search).toString())
				.toBe(expected.toString());
		}
	});
});
