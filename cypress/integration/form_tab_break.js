import doctype_with_tab_break from "../fixtures/doctype_with_tab_break";
const doctype_name = doctype_with_tab_break.name;
context("Form Tab Break", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
		return cy.insert_doc("DocType", doctype_with_tab_break, true);
	});
	it("Should switch tab and open correct tabs on validation error", () => {
		cy.new_form(doctype_name);
		// test tab switch
		cy.findByRole("tab", { name: "Tab 2" }).click();
		cy.findByText("Phone");
		cy.findByRole("tab", { name: "Details" }).click();
		cy.findByText("Name");

		// form should switch to the tab with un-filled mandatory field
		cy.fill_field("username", "Test");
		cy.findByRole("button", { name: "Save" }).click();
		cy.findByText("Missing Fields");
		cy.hide_dialog();
		cy.findByText("Phone");
		cy.fill_field("phone", "12345678");
		cy.findByRole("button", { name: "Save" }).click();

		// After save, first tab should have dashboard
		cy.get(".form-tabs > .nav-item").eq(0).click();
		cy.findByText("Profile");
	});
});
