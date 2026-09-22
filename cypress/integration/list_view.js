context("List View", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.setup_workflow");
			});
	});

	it("Keep checkbox checked after Refresh", { scrollBehavior: false }, () => {
		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.get(".list-header-subject > .list-subject > .list-check-all").click();
		cy.get("button[data-original-title='Reload List']").click();
		cy.get(".list-row-container .list-row-checkbox:checked").should("be.visible");
	});

	it('enables "Actions" button', { scrollBehavior: false }, () => {
		const actions = [
			"Approve",
			"Reject",
			"Export",
			"Assign To",
			"Clear Assignment",
			"Apply Assignment Rule",
			"Add Tags",
			"Print",
		];
		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.get(".list-header-subject > .list-subject > .list-check-all").click();
		cy.findByRole("button", { name: "Actions" }).click();
		cy.get(".dropdown-menu li:visible .dropdown-item")
			.should("have.length", 8)
			.each((el, index) => {
				cy.wrap(el).contains(actions[index]);
			})
			.then((elements) => {
				cy.intercept({
					method: "POST",
					url: "api/method/frappe.model.workflow.bulk_workflow_approval",
				}).as("bulk-approval");
				cy.wrap(elements).contains("Approve").click();
				cy.wait("@bulk-approval");
				cy.hide_dialog();
				cy.reload();
				cy.clear_filters();
				cy.get(".list-row-container:visible").should("contain", "Approved");
			});
	});

	it("flips sort order icon and title", { scrollBehavior: false }, () => {
		cy.go_to_list("ToDo");
		cy.clear_filters();

		// start from a known order, whatever the persisted list settings say
		cy.window()
			.its("cur_list.sort_selector")
			.then((sort_selector) => sort_selector.set_value(sort_selector.sort_by, "desc"));

		cy.get(".sort-selector .btn-order").as("order");
		cy.get("@order").should("have.attr", "title", "descending");
		cy.get("@order")
			.find(".sort-order use")
			.should("have.attr", "href", "#icon-sort-descending");

		cy.get("@order").click();
		cy.get("@order").should("have.attr", "data-value", "asc");
		cy.get("@order").should("have.attr", "title", "ascending");
		cy.get("@order")
			.find(".sort-order use")
			.should("have.attr", "href", "#icon-sort-ascending");
	});
});
