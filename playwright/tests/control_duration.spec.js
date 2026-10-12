import { test, expect } from "../support";

test.describe("Control Duration", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	function get_dialog_with_duration(desk, hide_days = 0, hide_seconds = 0) {
		return desk.dialog({
			title: "Duration",
			fields: [
				{
					fieldname: "duration",
					fieldtype: "Duration",
					hide_days: hide_days,
					hide_seconds: hide_seconds,
				},
			],
		});
	}

	test("should set duration", async ({ page, desk }) => {
		const dialog = await get_dialog_with_duration(desk);
		const input = page.locator(".frappe-control[data-fieldname=duration] input").first();
		const days = page.locator(".duration-input[data-duration=days]");
		const minutes = page.locator(".duration-input[data-duration=minutes]");

		await input.click();
		await days.click();
		await days.fill("45");
		await days.blur();
		await expect(input).toHaveValue("45d");
		await minutes.click();
		await minutes.fill("30");
		await minutes.blur();
		await expect(input).toHaveValue("45d 30m");
		await input.blur();
		await expect(page.locator(".duration-picker")).toHaveCount(0);
		expect(await dialog.evaluate((d) => d.get_value("duration"))).toBe(3889800);
		await desk.hide_dialog();
	});

	test("should hide days or seconds according to duration options", async ({ page, desk }) => {
		await get_dialog_with_duration(desk, 1, 1);
		await page.locator(".frappe-control[data-fieldname=duration] input").first().focus();
		await expect(page.locator(".duration-input[data-duration=hours]")).toBeVisible();
		await expect(page.locator(".duration-input[data-duration=days]")).toBeHidden();
		await expect(page.locator(".duration-input[data-duration=seconds]")).toBeHidden();
	});
});
