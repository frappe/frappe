import { test, expect } from "../support";

test.describe("Control MultiSelectPills", () => {
	test("does not suggest a value that is already selected", async ({ page, desk }) => {
		await page.goto("/app");
		await desk.ready();
		await desk.dialog({
			title: "MultiSelectPills",
			fields: [
				{
					label: "Select options",
					fieldname: "multiselect_pills",
					fieldtype: "MultiSelectPills",
					options: ["Option 1", "Option 2", "Option 3"],
				},
			],
		});

		const input = page.locator('.awesomplete > input[data-fieldname="multiselect_pills"]');
		const suggestions = input.locator("xpath=..").locator("li");
		await input.pressSequentially("2");
		await expect(suggestions).toHaveText("Option 2");
		await input.press("Enter");
		await input.pressSequentially("Option");

		await expect(suggestions).toHaveText(["Option 1", "Option 3"]);
	});
});
