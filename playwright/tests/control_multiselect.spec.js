import { test, expect } from "../support";

test.describe("Control MultiSelect", () => {
	test("does not suggest a value that is already selected", async ({ page, desk }) => {
		await page.goto("/app");
		await desk.ready();
		await desk.dialog({
			title: "MultiSelect",
			fields: [
				{
					label: "Select options",
					fieldname: "multiselect",
					fieldtype: "MultiSelect",
					options: ["Option 1", "Option 2", "Option 3"],
				},
			],
		});

		const input = page.locator(
			'.control-input > .awesomplete > input[data-fieldname="multiselect"]'
		);
		const suggestions = input.locator("xpath=..").locator("li");
		await input.pressSequentially("2");
		await expect(suggestions).toHaveText("Option 2");
		await input.press("Enter");
		await input.pressSequentially("Option");

		await expect(suggestions).toHaveText(["Option 1", "Option 3"]);
	});
});
