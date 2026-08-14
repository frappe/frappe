context("Filter Group", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/app/");
	});

	it("preserves numeric filter values with a comma decimal separator", () => {
		cy.window().its("frappe.ui.FilterGroup").should("exist");

		cy.window().then(async (win) => {
			const frappe = win.frappe;
			const $ = win.$;
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

				const [doctype, fieldname, condition, value] = filter_group.get_filters()[0];
				expect([doctype, fieldname, condition, value]).to.deep.equal([
					"Currency",
					"smallest_currency_fraction_value",
					"=",
					7.95,
				]);
			} finally {
				$parent.remove();
				frappe.boot.sysdefaults.number_format = original_number_format;
			}
		});
	});
});
