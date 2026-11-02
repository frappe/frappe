import { test, expect } from "../support";

test.describe("Grid dropdown position", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.call("frappe.tests.ui_test_helpers.create_webform_with_child_table_dropdown");
	});

	test("draws the child table dropdown next to the field on a scrolled web form", async ({
		page,
		desk,
	}) => {
		await desk.login("Administrator");
		await page.goto("/test-grid-dropdown/new");

		const cell = page.locator('.grid-body .rows .grid-row .col[data-fieldname="item"]');
		const input = cell.locator("input").first();
		const list = page.locator(".awesomplete > ul:visible");
		await page.locator(".grid-add-row").click();
		await cell.first().click();
		await input.pressSequentially("a");
		await expect(list.locator("li").first()).toBeVisible();

		// the dropdown is positioned by hand, and used to be displaced by the page scroll
		await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(100);

		const input_bottom = await input.evaluate((el) => el.getBoundingClientRect().bottom);
		const list_top = await list.evaluate((el) => el.getBoundingClientRect().top);
		const gap = list_top - input_bottom;
		expect(gap, "gap between field and dropdown").toBeGreaterThanOrEqual(-20);
		expect(gap, "gap between field and dropdown").toBeLessThanOrEqual(20);
	});

	test("moves the dropdown back when a filled cell is left without opening it", async ({
		page,
		desk,
	}) => {
		await desk.login("Administrator");
		await page.goto("/test-grid-dropdown/new");

		const cell = page
			.locator('.grid-body .rows .grid-row .col[data-fieldname="item"]')
			.first();
		const input = cell.locator("input").first();
		const parked = page.locator(".grid-field > .awesomplete");
		await page.locator(".grid-add-row").click();
		await cell.click();
		await input.pressSequentially("a");
		await page.locator(".awesomplete > ul:visible li").first().click();
		await expect(input).not.toHaveValue("");
		await input.blur();
		await expect(parked).toHaveCount(0);

		await input.focus();
		await expect(parked).toHaveCount(1);
		await expect(page.locator(".awesomplete > ul:visible")).toHaveCount(0);

		await input.fill("a");
		await expect(parked.locator("ul li")).toHaveCount(3);
		await input.press("Escape");
		await input.fill("c");
		await expect(parked.locator("ul li").first()).toBeVisible();

		await input.blur();
		await expect(parked).toHaveCount(0);
		await expect(cell.locator(".awesomplete > ul")).toHaveCount(1);
	});
});
