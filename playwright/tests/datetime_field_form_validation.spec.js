import { test, expect } from "../support";

test.describe("Datetime Field Validation", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_datetime_test_doctype");
	});

	test("datetime field form validation", async ({ page, desk, api }) => {
		await page.goto("/desk");
		await desk.ready();
		const doc = (await api.call("frappe.tests.ui_test_helpers.create_datetime_test_record"))
			.message;

		await page.goto(`/desk/test-datetime-precision/${doc.name}`);
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await expect.poll(() => page.evaluate(() => window.cur_frm?.is_dirty())).toBe(false);
		await expect(page.locator('[data-testid="page-status"]')).toContainText("Draft");
		await expect(page.locator(".primary-action[data-label='Submit']")).toBeVisible();
	});
});
