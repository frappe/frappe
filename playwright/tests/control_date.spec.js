import { test, expect } from "../support";

test.describe("Date Control", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk");
		await desk.ready();
	});

	function get_dialog(desk, date_field_options) {
		return desk.dialog({
			title: "Date",
			animate: false,
			fields: [
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Date",
					in_list_view: 1,
					...date_field_options,
				},
			],
		});
	}

	function get_date_value(page) {
		return page.evaluate(() => cur_dialog.fields_dict.date.value);
	}

	test("Selecting a date from the datepicker & check prev & next button", async ({
		page,
		desk,
	}) => {
		await get_dialog(desk);
		const input = desk.get_field("date", "Date");
		await input.click();
		await page.locator(".datepicker--nav-title").click();
		await page.locator(".datepicker--nav-title").click();

		await page
			.locator(
				'.datepicker--years > .datepicker--cells > .datepicker--cell[data-year="2020"]'
			)
			.click();
		await page
			.locator(
				'.datepicker--months > .datepicker--cells > .datepicker--cell[data-month="0"]'
			)
			.click();
		await page
			.locator('.datepicker--days > .datepicker--cells > .datepicker--cell[data-date="15"]')
			.click();

		await expect.poll(() => get_date_value(page)).toBe("2020-01-15");

		await input.click();
		await page.locator(".datepicker--nav-action[data-action=next]").click();
		await page.locator('.datepicker--cell[data-date="15"]').click();

		await expect.poll(() => get_date_value(page)).toBe("2020-02-15");

		await input.click();
		await page.locator(".datepicker--nav-action[data-action=prev]").click();
		await page.locator('.datepicker--cell[data-date="15"]').click();

		await expect.poll(() => get_date_value(page)).toBe("2020-01-15");
	});

	test('Clicking on "Today" button gives todays date', async ({ page, desk }) => {
		await get_dialog(desk);
		await desk.get_field("date", "Date").click();

		await page.locator(".datepicker--button").click();

		const today = await page.evaluate(() => frappe.datetime.get_today());
		await expect.poll(() => get_date_value(page)).toBe(today);
	});
});
