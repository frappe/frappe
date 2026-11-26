import { test, expect } from "../support";

test.describe("Date Range Control", () => {
	test("Selecting a date range from the datepicker", async ({ page, desk }) => {
		await page.goto("/desk");
		await desk.ready();

		await desk.dialog({
			title: "Date Range",
			fields: [
				{
					label: "Date Range",
					fieldname: "date_range",
					fieldtype: "Date Range",
				},
			],
		});
		await desk.get_field("date_range", "Date Range").click();
		await page.locator(".air-datepicker-nav--title").click();
		await page.locator(".air-datepicker-nav--title").click();

		await page.locator('.air-datepicker-cell.-year-[data-year="2020"]').click();
		await page.locator('.air-datepicker-cell.-month-[data-month="0"]').click();
		await page.locator('.air-datepicker-cell.-day-[data-date="1"]').first().click();
		await page.locator('.air-datepicker-cell.-day-[data-date="15"]').first().click();

		await expect
			.poll(() => page.evaluate(() => cur_dialog.get_value("date_range")))
			.toEqual(["2020-01-01", "2020-01-15"]);
	});
});
