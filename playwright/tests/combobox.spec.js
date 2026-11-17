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

	test.describe("near the bottom of the screen", () => {
		test.use({ viewport: { width: 800, height: 500 } });

		test("keeps the list above the field while a search shrinks it", async ({
			page,
			desk,
		}) => {
			await page.goto("/desk/website");
			await desk.ready();
			await page.evaluate(() => {
				const fruits = ["Apple", "Apricot", "Banana", "Cherry", "Grape", "Guava"];
				const names = [...fruits, ...Array.from({ length: 24 }, (_, i) => `Fruit ${i}`)];
				const combobox = new frappe.ui.Combobox({
					options: names.map((name) => ({ label: name, value: name })),
				});
				combobox.$trigger
					.addClass("test-combobox")
					.css({
						position: "fixed",
						left: "300px",
						bottom: "140px",
						width: "240px",
						zIndex: 1050,
					})
					.appendTo("body");
			});

			const trigger = page.locator(".test-combobox");
			const panel = page.locator(".es-combobox__panel[data-state='open']");
			await trigger.click();
			await expect(panel).toHaveAttribute("data-side", "top");

			// three rows would fit below the field, but the list stays where it opened
			await panel.locator(".es-combobox__input").fill("ap");
			await expect(panel.getByRole("option")).toHaveCount(3);
			await expect(panel).toHaveAttribute("data-side", "top");
			await expect
				.poll(async () => {
					const field = await trigger.boundingBox();
					const list = await panel.boundingBox();
					return Math.round(field.y - (list.y + list.height));
				})
				.toBe(4);
		});
	});
});
