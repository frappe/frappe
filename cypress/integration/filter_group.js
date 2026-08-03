context("Filter Group", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	it("preserves numeric filter values with a comma decimal separator", () => {
		cy.window().then(async ({ frappe, $ }) => {
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

				expect(filter_group.get_filters()).to.deep.equal([
					["Currency", "smallest_currency_fraction_value", "=", 7.95],
				]);
			} finally {
				$parent.remove();
				frappe.boot.sysdefaults.number_format = original_number_format;
			}
		});
	});
});
