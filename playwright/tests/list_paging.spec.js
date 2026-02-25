const { test, expect } = require("@playwright/test");
const { login, frappeCall } = require("../utils");

test.describe("List Paging", () => {
	test.beforeAll(async ({ browser }) => {
		const context = await browser.newContext();
		const page = await context.newPage();
		await login(page);
		await page.goto("/desk/website");

		// Create multiple todo records for testing pagination
		await frappeCall(page, "frappe.tests.ui_test_helpers.create_multiple_todo_records");

		await context.close();
	});

	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test("test load more with count selection buttons", async ({ page }) => {
		await page.goto("/desk/todo/view/report");

		// Clear any existing filters
		const clearFiltersBtn = page.locator(".filter-section .btn-secondary");
		if (await clearFiltersBtn.isVisible()) {
			await clearFiltersBtn.click();
			await page.waitForTimeout(500);
		}

		// Check initial count (20 records)
		await expect(page.locator(".list-paging-area .list-count")).toContainText("20 of", {
			timeout: 10000,
		});

		// Load more - should show 40
		await page.locator(".list-paging-area .btn-more").click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("40 of");

		// Load more - should show 60
		await page.locator(".list-paging-area .btn-more").click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("60 of");

		// Select 100 per page
		await page.locator('.list-paging-area .btn-group .btn-paging[data-value="100"]').click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("100 of");

		// Load more - should show 200
		await page.locator(".list-paging-area .btn-more").click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("200 of");

		// Load more - should show 300
		await page.locator(".list-paging-area .btn-more").click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("300 of");

		// Check if refresh works after load more
		await page
			.locator('.page-head .standard-actions [data-original-title="Reload List"]')
			.click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("300 of");

		// Select 500 per page
		await page.locator('.list-paging-area .btn-group .btn-paging[data-value="500"]').click();
		await page.waitForTimeout(500);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("500 of");

		// Load more - should show 1,000
		await page.locator(".list-paging-area .btn-more").click();
		await page.waitForTimeout(1000);
		await expect(page.locator(".list-paging-area .list-count")).toContainText("1,000 of");
	});
});
