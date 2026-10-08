import { test, expect } from "../support";

test.describe("Control Autocomplete", () => {
	const get_dialog_with_autocomplete = async (page, desk, fieldname, options) => {
		await page.goto("/desk");
		await desk.ready();
		return desk.dialog({
			title: "Autocomplete",
			fields: [
				{
					label: "Select an option",
					fieldname: fieldname,
					fieldtype: "Autocomplete",
					options: options,
				},
			],
		});
	};

	const select_second_option = async (page, fieldname) => {
		const input = page.locator(
			`.control-input > .awesomplete > input[data-fieldname=${fieldname}]`
		);
		await input.pressSequentially("2");
		await expect(input.locator("xpath=..").locator("li")).toHaveText("Option 2");
		await input.press("Enter");
	};

	test("should set the valid value", async ({ page, desk }) => {
		const fieldname = "autocomplete_1";
		const dialog = await get_dialog_with_autocomplete(page, desk, fieldname, [
			"Option 1",
			"Option 2",
			"Option 3",
		]);
		await select_second_option(page, fieldname);
		await expect
			.poll(() => dialog.evaluate((d, fieldname) => d.get_value(fieldname), fieldname))
			.toBe("Option 2");
		await dialog.evaluate((d) => {
			d.clear();
			d.hide();
		});
	});

	test("should set the valid value with different label", async ({ page, desk }) => {
		const fieldname = "autocomplete_2";
		const dialog = await get_dialog_with_autocomplete(page, desk, fieldname, [
			{ label: "Option 1", value: "option_1" },
			{ label: "Option 2", value: "option_2" },
		]);
		await select_second_option(page, fieldname);
		await expect
			.poll(() => dialog.evaluate((d, fieldname) => d.get_value(fieldname), fieldname))
			.toBe("option_2");
		await dialog.evaluate((d) => {
			d.clear();
			d.hide();
		});
	});
});
