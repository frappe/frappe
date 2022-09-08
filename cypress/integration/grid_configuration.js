context("Grid Configuration", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/app/doctype/User");
	});
	it("Set user wise grid settings", () => {
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields"]').as("table");
		cy.get("@table").find(".icon-sm").click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields_html"]').as("modal");
		cy.get("@modal").find(".add-new-fields").click();
		cy.wait(100);
		cy.get('[type="checkbox"][data-unit="read_only"]').check();
		cy.findByRole("button", { name: "Add" }).click();
		cy.wait(100);
		cy.get('[data-fieldname="options"]').invoke("attr", "value", "1");
		cy.get('.form-control.column-width[data-fieldname="options"]').trigger("change");
		cy.findByRole("button", { name: "Update" }).click();
		cy.wait(200);
		cy.get('[title="Read Only"').should("be.visible");
	});
});
