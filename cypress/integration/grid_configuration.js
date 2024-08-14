context("Grid Configuration", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/app/website-settings");
	});
	it("Set user wise grid settings", () => {
		cy.findByRole("tab", { name: "Navbar" }).click();
		cy.get('.form-section[data-fieldname="fields_section"]').click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields"]').as("table");
		cy.get("@table").find(".icon-sm").click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields_html"]').as("modal");
		cy.get("@modal").find(".add-new-fields").click();
		cy.wait(100);
		cy.get('[type="checkbox"][data-unit="right"]').check();
		cy.findByRole("button", { name: "Add" }).click();
		cy.wait(100);
		cy.get('[data-fieldname="parent_label"]').invoke("attr", "value", "1");
		cy.get('.form-control.column-width[data-fieldname="parent_label"]').trigger("change");
		cy.findByRole("button", { name: "Update" }).click();
		cy.wait(200);
		cy.get('[title="Align Right"').should("be.visible");
	});
});
