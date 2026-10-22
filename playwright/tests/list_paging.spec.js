import { test, expect } from "../support";

// the page-size pills are an es TabButtons radio group — no data-value
// attribute, so match by exact pill text
const paging_pill = (page, value) =>
	page
		.locator(".list-paging-area .es-pill")
		.filter({ hasText: new RegExp("^\\s*" + value + "\\s*$") })
		.first();

test.describe("List Paging", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_multiple_todo_records");
	});

	test("test load more with count selection buttons", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/report");
		await desk.clear_filters();

		const list_count = page.locator(".list-paging-area .list-count");
		const load_more = page.locator(".list-paging-area .btn-more");

		await expect(list_count).toContainText("20 of");
		await load_more.click();
		await expect(list_count).toContainText("40 of");
		await load_more.click();
		await expect(list_count).toContainText("60 of");

		await paging_pill(page, 100).click();

		await expect(list_count).toContainText("100 of");
		await load_more.click();
		await expect(list_count).toContainText("200 of");
		await load_more.click();
		await expect(list_count).toContainText("300 of");

		await page
			.locator('.page-head .standard-actions [data-original-title="Reload List"]')
			.click();
		await expect(list_count).toContainText("300 of");

		await paging_pill(page, 500).click();

		await expect(list_count).toContainText("500 of");
		await load_more.click();

		await expect(list_count).toContainText("1,000 of");
	});
});
