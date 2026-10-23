import { test, expect } from "../support";

// frappe.ui.Combobox on its own, with rows filtered in the browser.
test.describe("Combobox", () => {
	test("finds a group's rows by the group's name", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
		await page.evaluate(() => {
			const combobox = new frappe.ui.Combobox({
				options: [
					{ label: "Apple", value: "apple" },
					{
						group: "Citrus",
						options: [
							{ label: "Lemon", value: "lemon" },
							{ label: "Orange", value: "orange" },
						],
					},
				],
			});
			combobox.$trigger
				.addClass("test-combobox")
				.appendTo(".page-container:visible .page-body");
		});

		const panel = page.locator(".es-combobox__panel[data-state='open']");
		const options = panel.getByRole("option");
		await page.locator(".test-combobox").click();
		await panel.locator(".es-combobox__input").fill("citrus");
		await expect(options).toHaveText(["Lemon", "Orange"]);

		// a row's own text still narrows within the group
		await panel.locator(".es-combobox__input").fill("lem");
		await expect(options).toHaveText(["Lemon"]);
	});
});
