import { test, expect } from "../support";

test.describe("Filter Group", () => {
	test("preserves numeric filter values with a comma decimal separator", async ({
		page,
		desk,
	}) => {
		await page.goto("/app/website");
		await desk.ready();

		const filter = await page.evaluate(async () => {
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

				return filter_group.get_filters()[0].slice(0, 4);
			} finally {
				$parent.remove();
				frappe.boot.sysdefaults.number_format = original_number_format;
			}
		});

		expect(filter).toEqual(["Currency", "smallest_currency_fraction_value", "=", 7.95]);
	});
});
