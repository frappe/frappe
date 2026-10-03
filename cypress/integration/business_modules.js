context("Business Modules", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
		cy.call("frappe.tests.ui_test_helpers.create_business_module_doctypes");
	});

	const field = (fieldname) =>
		cy.get(`.form-layout .frappe-control[data-fieldname="${fieldname}"]`);
	const column = (fieldname) =>
		cy.get(
			`.frappe-control[data-fieldname="items"] .grid-heading-row .grid-static-col[data-fieldname="${fieldname}"]`
		);
	const hide_module_fields = (modules) =>
		cy
			.window()
			.its("cur_frm")
			.then((frm) => frm.hide_module_fields(modules));

	it("hides tagged fields when their module is off and shows them when it is on", () => {
		cy.new_form("Test Module Fields");
		field("plain").should("be.visible");
		field("tagged").should("be.visible");
		column("tagged_col").should("be.visible");

		hide_module_fields(["Stock"]);
		field("plain").should("be.visible");
		field("tagged").should("not.be.visible");
		column("tagged_col").should("not.exist");

		hide_module_fields([]);
		field("tagged").should("be.visible");
		column("tagged_col").should("be.visible");
	});

	it("keeps hiding after the form refreshes", () => {
		cy.new_form("Test Module Fields");
		hide_module_fields(["Stock"]);
		field("tagged").should("not.be.visible");

		cy.window()
			.its("cur_frm")
			.then((frm) => frm.refresh());
		field("tagged").should("not.be.visible");
		field("plain").should("be.visible");
	});
});
