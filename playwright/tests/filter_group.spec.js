import { test, expect } from "../support";

test.describe("Filter Group", () => {
	test("preserves numeric filter values with a comma decimal separator", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/website");
		await desk.ready();

		const filters = await page.evaluate(async () => {
			const original_number_format = frappe.boot.sysdefaults.number_format;
			frappe.boot.sysdefaults.number_format = "#.###,##";
			await frappe.model.with_doctype("Currency");

			const $parent = $("<div>").appendTo("body");
			try {
				const filter_group = new frappe.ui.FilterGroup({
					parent: $parent,
					doctype: "Currency",
					on_change: () => {},
				});

				await filter_group.add_filter(
					"Currency",
					"smallest_currency_fraction_value",
					"=",
					7.95
				);

				return filter_group.get_filters();
			} finally {
				$parent.remove();
				frappe.boot.sysdefaults.number_format = original_number_format;
			}
		});

		expect(filters).toEqual([["Currency", "smallest_currency_fraction_value", "=", 7.95]]);
	});

	test("applies a combobox MultiSelect pick in a filter row", async ({ page, desk }) => {
		await page.goto("/desk/website");
		await desk.ready();
		await page.evaluate(async () => {
			// the combobox for this page only: other tests run with the setting as it is
			frappe.sys_defaults.enable_combobox_link_field = 1;
			await frappe.model.with_doctype("ToDo");
			const $parent = $('<div class="test-filter-group">').appendTo(
				".page-container:visible .page-body"
			);
			window.test_filter_group = new frappe.ui.FilterGroup({
				parent: $parent,
				doctype: "ToDo",
				on_change: () => window.test_filter_changes++,
			});
			await window.test_filter_group.add_filter("ToDo", "priority", "in", ["High"]);
		});
		// only the pick counts, not the row being added
		await page.waitForFunction(() => frappe.request.ajax_count === 0);
		await page.evaluate(() => (window.test_filter_changes = 0));

		await page.locator(".test-filter-group .filter-field .es-combobox").click();
		await page
			.locator(".es-combobox__panel[data-state='open']")
			.getByRole("option", { name: "Medium", exact: true })
			.click();

		await expect.poll(() => page.evaluate(() => window.test_filter_changes)).toBe(1);
		expect(await page.evaluate(() => window.test_filter_group.get_filters())).toEqual([
			["ToDo", "priority", "in", ["High", "Medium"]],
		]);
	});
});
