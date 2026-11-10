import { test, expect } from "../support";

test.describe("Control Rating", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	function get_dialog_with_rating(desk) {
		return desk.dialog({
			title: "Rating",
			fields: [
				{
					fieldname: "rate",
					fieldtype: "Rating",
					options: 7,
				},
			],
		});
	}

	test("click on the star rating to record value", async ({ page, desk }) => {
		const dialog = await get_dialog_with_rating(desk);

		const star = page.locator("div.rating > svg .right-half").first();
		await star.click();
		await expect(star).toHaveClass(/(^|\s)star-click(\s|$)/);

		expect(await dialog.evaluate((d) => d.get_value("rate"))).toBe(1 / 7);
		await dialog.evaluate((d) => d.hide());
	});

	test("hover on the star", async ({ page, desk }) => {
		await get_dialog_with_rating(desk);

		const star = page.locator("div.rating > svg .right-half").first();
		await star.hover();
		await expect(star).toHaveClass(/(^|\s)star-hover(\s|$)/);
		await page.locator(".modal:visible .modal-title").hover();
		await expect(star).not.toHaveClass(/(^|\s)star-hover(\s|$)/);
	});

	test("check number of stars in rating", async ({ page, desk }) => {
		await get_dialog_with_rating(desk);

		await expect(page.locator("div.rating").first().locator("> svg")).toHaveCount(7);
	});
});
