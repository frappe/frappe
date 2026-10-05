import { test, expect } from "../support";

test.describe("Control Icon", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	async function open_icon_picker(page, desk) {
		const dialog = await desk.dialog({
			title: "Icon",
			fields: [
				{
					label: "Icon",
					fieldname: "icon",
					fieldtype: "Icon",
				},
			],
		});
		await page.locator(".frappe-control[data-fieldname=icon]").getByRole("textbox").click();
		await expect(page.locator(".icon-picker")).toBeVisible();
		return dialog;
	}

	test("should set icon", async ({ page, desk }) => {
		const dialog = await open_icon_picker(page, desk);
		const input = page.locator(".frappe-control[data-fieldname=icon]").getByRole("textbox");

		await page.locator(".icon-picker .icon-wrapper[id=heart-pulse]").first().click();
		await expect(input).toHaveValue("heart-pulse");
		expect(await dialog.evaluate((d) => d.get_value("icon"))).toBe("heart-pulse");

		await page.locator(".icon-picker .icon-wrapper[id=heart]").first().click();
		await expect(input).toHaveValue("heart");
		expect(await dialog.evaluate((d) => d.get_value("icon"))).toBe("heart");
	});

	test("search for icon and clear search input", async ({ page, desk }) => {
		await open_icon_picker(page, desk);

		const search_text = "ed";
		const search = page.locator(".icon-picker .search-icons > input");
		await search.click();
		await search.pressSequentially(search_text);
		const matching = await page
			.locator(`.icon-section .icon-wrapper[id*='${search_text}']`)
			.count();
		expect(matching).toBeGreaterThan(0);
		await expect(page.locator(".icon-section .icon-wrapper:not(.hidden)")).toHaveCount(
			matching
		);

		await search.press("ControlOrMeta+a");
		await search.press("Delete");
		await search.blur();
		await expect(page.locator(".icon-section .icon-wrapper").first()).toBeAttached();
		await expect(page.locator(".icon-section .icon-wrapper.hidden")).toHaveCount(0);
	});
});
