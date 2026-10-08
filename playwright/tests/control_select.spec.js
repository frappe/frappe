import { test, expect } from "../support";

test.describe("Control Select", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	test("toggles placholder on clicking an option", async ({ page, desk }) => {
		const dialog = await desk.dialog({
			title: "Select",
			fields: [
				{
					fieldname: "select_control",
					fieldtype: "Select",
					placeholder: "Select an Option",
					options: ["", "Option 1", "Option 2", "Option 2"],
				},
			],
		});

		const control = page.locator(
			".frappe-control[data-fieldname=select_control] .control-input"
		);
		const select = control.locator("select");
		const placeholder = control.locator(".placeholder");

		await expect(control.locator(".select-icon")).toBeAttached();
		await expect(placeholder).toHaveCSS("display", "block");
		await select.selectOption("Option 1");
		await expect(select).toHaveValue("Option 1");
		await expect(placeholder).toHaveCSS("display", "none");
		await select.evaluate((el) => $(el).val(""));
		await expect(select).not.toHaveValue("Option 1");
		await expect(placeholder).toHaveCSS("display", "block");

		await dialog.evaluate((d) => d.hide());
	});
});
