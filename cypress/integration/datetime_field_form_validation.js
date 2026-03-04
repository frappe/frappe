context("Datetime Field Validation", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
		cy.get(".page-container").should("exist");
		cy.window().should("have.property", "frappe");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_datetime_test_doctype");
			});
	});

	it("datetime field form validation", () => {
		// after loading a precise timestamp that has been set in backend, the
		// form should not get dirty by (accidentally) making it a less precise timestamp.
		cy.visit("/desk");
		cy.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_datetime_test_record");
			})
			.then((doc) => {
				cy.visit(`/desk/test-datetime-precision/${doc.name}`);
				cy.get("body").should("have.attr", "data-ajax-state", "complete");
				cy.window()
					.its("cur_frm")
					.then((frm) => {
						expect(frm.is_dirty()).to.be.false;
					});
				cy.get(".indicator-pill").should("contain", "Draft");
				cy.get(".btn-primary[data-label='Submit']").should("be.visible");
			});
	});
});
