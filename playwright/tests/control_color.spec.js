import { test, expect } from "../support";

async function click_at_offset(locator, x, y) {
	const box = await locator.boundingBox();
	await locator.dispatchEvent("click", { clientX: box.x + x, clientY: box.y + y });
}

test.describe("Control Color", () => {
	test("Verifying if the color control is selecting correct", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();

		const dialog = await desk.dialog({
			title: "Color",
			fields: [
				{
					label: "Color",
					fieldname: "color",
					fieldtype: "Color",
				},
			],
		});
		const get_color = () => dialog.evaluate((d) => d.get_value("color"));
		const color_map = page.locator(".color-map");
		const hue_map = page.locator(".hue-map");

		await page.getByPlaceholder("Choose a color").click();

		await page.locator('.swatch[data-color="#077ddf"]').click();
		await expect(color_map).toHaveCSS("color", "rgb(7, 125, 223)");
		await expect(hue_map).toHaveCSS("color", "rgb(0, 140, 255)");
		expect(await get_color()).toBe("#077ddf");

		await page.locator('.swatch[data-color="#ce2c2c"]').click();
		await expect(color_map).toHaveCSS("color", "rgb(206, 44, 44)");
		await expect(hue_map).toHaveCSS("color", "rgb(255, 0, 0)");
		expect(await get_color()).toBe("#ce2c2c");

		await click_at_offset(color_map.locator("> .color-selector"), 65, 87);
		await expect(color_map).toHaveCSS("color", "rgb(61, 0, 0)");
		expect(await get_color()).toBe("#3d0000");

		await click_at_offset(hue_map.locator("> .hue-selector"), 35, -1);
		await expect(color_map).toHaveCSS("color", "rgb(61, 46, 0)");
		await expect(hue_map).toHaveCSS("color", "rgb(255, 191, 0)");
		await click_at_offset(color_map.locator("> .color-selector"), 55, 12);
		await expect(color_map).toHaveCSS("color", "rgb(54, 40, 0)");
		expect(await get_color()).toBe("#362800");

		const input = desk.get_field("color", "Color");
		await input.click();
		await input.press("ControlOrMeta+a");
		await input.clear();
		await expect(input).toHaveAttribute("placeholder", /Choose a color/);
	});
});
