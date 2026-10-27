import { test, expect } from "../support";
import { shown_dialog } from "../support/shown_dialog";

test.describe("Dialog stacking", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	test("a confirm opened over a message can be answered", async ({ page }) => {
		await shown_dialog(await page.evaluateHandle(() => frappe.msgprint("Saved")));
		const confirm = await page.evaluateHandle(() =>
			frappe.confirm("Delete it?", () => {
				window.confirmed = true;
			})
		);
		await shown_dialog(confirm);

		await page
			.locator(".modal.show")
			.filter({ hasText: "Delete it?" })
			.getByRole("button", { name: "Yes" })
			.click();

		await expect.poll(() => page.evaluate(() => window.confirmed)).toBe(true);
	});

	test("a dialog opened again shows above a newer one", async ({ page }) => {
		const first = await page.evaluateHandle(() => {
			const d = new frappe.ui.Dialog({
				title: "First",
				primary_action_label: "Done",
				primary_action: () => {
					window.first_done = true;
				},
			});
			d.show();
			return d;
		});
		await shown_dialog(first);
		await first.evaluate((d) => d.hide());
		await expect.poll(() => first.evaluate((d) => d.display)).toBe(false);

		await shown_dialog(
			await page.evaluateHandle(() =>
				new frappe.ui.Dialog({ title: "Second", size: "large" }).show()
			)
		);
		await first.evaluate((d) => d.show());
		await shown_dialog(first);

		await page
			.locator(".modal.show")
			.filter({ hasText: "First" })
			.getByRole("button", { name: "Done" })
			.click();

		await expect.poll(() => page.evaluate(() => window.first_done)).toBe(true);
	});
});
