import { test, expect } from "../support";
import { shown_dialog } from "../support/shown_dialog";

// The first get_values() refreshes a mandatory input whose model value is still empty, which
// clears the typed text. A primary action that reads the dialog again sees an empty field.
async function type_without_change(dialog, fieldname, value) {
	await dialog.evaluate(
		(d, [fieldname, value]) => d.fields_dict[fieldname].$input.val(value),
		[fieldname, value]
	);
}

test.describe("Dialog primary action", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
	});

	test("frappe.prompt passes typed values to the callback", async ({ page }) => {
		const dialog = await page.evaluateHandle(() =>
			frappe.prompt(
				{ label: "Title", fieldname: "title", fieldtype: "Data", reqd: 1 },
				(v) => {
					window.prompt_values = v;
				}
			)
		);
		await shown_dialog(dialog);
		await type_without_change(dialog, "title", "Prompt Title");
		await dialog.evaluate((d) => d.get_primary_btn().click());

		await expect
			.poll(() => page.evaluate(() => window.prompt_values))
			.toEqual({
				title: "Prompt Title",
			});
	});

	test("frappe.prompt still blocks an empty mandatory field", async ({ page }) => {
		const dialog = await page.evaluateHandle(() =>
			frappe.prompt(
				{ label: "Title", fieldname: "title", fieldtype: "Data", reqd: 1 },
				(v) => {
					window.prompt_values = v;
				}
			)
		);
		await shown_dialog(dialog);
		await dialog.evaluate((d) => d.get_primary_btn().click());

		await expect(page.locator(".msgprint-dialog")).toContainText("Title");
		expect(await page.evaluate(() => window.prompt_values)).toBeUndefined();
	});

	test("quick entry keeps typed values", async ({ page }) => {
		const dialog = await page.evaluateHandle(() =>
			frappe.ui.form.make_quick_entry(
				"Note",
				(doc) => {
					window.quick_entry_doc = doc;
				},
				null,
				null,
				true,
				true
			)
		);
		await shown_dialog(dialog);
		await type_without_change(dialog, "title", "Quick Entry Title");
		await dialog.evaluate((d) => d.get_primary_btn().click());

		await expect
			.poll(() => page.evaluate(() => window.quick_entry_doc?.title))
			.toBe("Quick Entry Title");
	});
});
