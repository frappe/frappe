import { test, expect } from "../support";

test.describe("Control Barcode", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	function get_dialog_with_barcode(desk) {
		return desk.dialog({
			title: "Barcode",
			fields: [
				{
					label: "Barcode",
					fieldname: "barcode",
					fieldtype: "Barcode",
				},
			],
		});
	}

	test("should generate barcode on setting a value", async ({ page, desk }) => {
		const dialog = await get_dialog_with_barcode(desk);

		const control = page.locator(".frappe-control[data-fieldname=barcode]");
		const input = control.getByRole("textbox");
		await input.pressSequentially("123456789");
		await input.blur();
		await expect(control.locator('svg[data-barcode-value="123456789"]')).not.toHaveCount(0);

		const value = await dialog.evaluate((d) => d.get_value("barcode"));
		expect(value).toContain("<svg");
		expect(value).toContain('data-barcode-value="123456789"');
	});

	test("should reset when input is cleared", async ({ page, desk }) => {
		const dialog = await get_dialog_with_barcode(desk);

		const control = page.locator(".frappe-control[data-fieldname=barcode]");
		const input = control.getByRole("textbox");
		await input.pressSequentially("123456789");
		await input.blur();
		await input.clear();
		await input.blur();
		await expect(control.locator('svg[data-barcode-value="123456789"]')).toHaveCount(0);

		expect(await dialog.evaluate((d) => d.get_value("barcode"))).toBe("");
	});
});
