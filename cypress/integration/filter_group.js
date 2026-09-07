context("Filter Group", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	it("does not apply form link filters to filter value searches", () => {
		cy.window().then(({ frappe, $ }) => {
			const df = {
				parent: "Test Document",
				fieldname: "group",
				label: "Group",
				fieldtype: "Link",
				options: "Test Tree",
				link_filters: JSON.stringify([["Test Tree", "is_group", "=", 0]]),
			};
			const $parent = $('<div><div class="filter-edit-area"></div></div>').appendTo("body");
			try {
				const filter = new frappe.ui.Filter({
					parent: $parent,
					parent_doctype: df.parent,
					doctype: df.parent,
					fieldname: df.fieldname,
					filter_fields: [df],
					condition: "=",
					on_change: () => {},
				});

				for (const condition of [
					"=",
					"descendants of",
					"descendants of (inclusive)",
					"not descendants of",
					"ancestors of",
					"not ancestors of",
					"!=",
				]) {
					filter.set_condition(condition, true);
					expect(filter.field.get_search_args("Parent").filters, condition).to.be
						.undefined;
				}

				filter.set_condition("like", true);
				filter.set_condition("descendants of", true);
				expect(filter.field.get_search_args("Parent").filters).to.be.undefined;

				const form_control = frappe.ui.form.make_control({
					df,
					parent: $parent,
					render_input: true,
				});
				expect(form_control.get_search_args("Child").filters).to.deep.equal({
					is_group: ["=", 0],
				});
			} finally {
				$parent.remove();
			}
		});
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
