import { test, expect } from "../support";
import { shown_dialog } from "../support/shown_dialog";

test.describe("Dialog stacking", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	test("a dialog opened over another covers it with its backdrop", async ({ page }) => {
		const parent = await shown_dialog(
			await page.evaluateHandle(() => new frappe.ui.Dialog({ title: "Parent" }).show())
		);
		await shown_dialog(
			await page.evaluateHandle(() => new frappe.ui.Dialog({ title: "Child" }).show())
		);

		const [parent_z, backdrop_z] = await parent.evaluate((d) => [
			cint(getComputedStyle(d.$wrapper[0]).zIndex),
			cint(
				getComputedStyle([...document.querySelectorAll(".modal-backdrop")].at(-1)).zIndex
			),
		]);

		expect(backdrop_z).toBeGreaterThan(parent_z);
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
