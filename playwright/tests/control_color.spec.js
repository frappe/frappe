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

		await page.locator('[style="background-color: rgb(79, 157, 217);"]').click();
		await expect(color_map).toHaveCSS("color", "rgb(79, 157, 217)");
		await expect(hue_map).toHaveCSS("color", "rgb(0, 145, 255)");
		expect(await get_color()).toBe("#4F9DD9");

		await page.locator('[style="background-color: rgb(203, 41, 41);"]').click();
		await expect(color_map).toHaveCSS("color", "rgb(203, 41, 41)");
		await expect(hue_map).toHaveCSS("color", "rgb(255, 0, 0)");
		expect(await get_color()).toBe("#CB2929");

		await click_at_offset(color_map.locator("> .color-selector"), 65, 87);
		await expect(color_map).toHaveCSS("color", "rgb(56, 0, 0)");
		expect(await get_color()).toBe("#380000");

		await click_at_offset(hue_map.locator("> .hue-selector"), 35, -1);
		await expect(color_map).toHaveCSS("color", "rgb(56, 45, 0)");
		await expect(hue_map).toHaveCSS("color", "rgb(255, 204, 0)");
		await click_at_offset(color_map.locator("> .color-selector"), 55, 12);
		await expect(color_map).toHaveCSS("color", "rgb(46, 37, 0)");
		expect(await get_color()).toBe("#2e2500");

		const input = desk.get_field("color", "Color");
		await input.click();
		await input.press("ControlOrMeta+a");
		await input.clear();
		await expect(input).toHaveAttribute("placeholder", /Choose a color/);
	});
});
