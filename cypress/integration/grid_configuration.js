context("Grid Configuration", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/app/website-settings");
	});
	it("Set user wise grid settings", () => {
		cy.findByRole("tab", { name: "Navbar" }).click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="top_bar_items"]').as("table");
		cy.get("@table").find(".icon-sm").click();
		cy.wait(100);
		cy.get('.frappe-control[data-fieldname="fields_html"]').as("modal");
		cy.get("@modal").find(".add-new-fields").click();
		cy.wait(100);
		cy.get('[type="checkbox"][data-unit="right"]').check();
		cy.wait(100);
		cy.findByRole("button", { name: "Add" }).wait(100).click();
		cy.get('[data-fieldname="parent_label"]').invoke("attr", "value", "1");
		cy.get('.form-control.column-width[data-fieldname="parent_label"]').trigger("change");
		cy.findByRole("button", { name: "Update" }).click();
		cy.wait(200);
		cy.get('[title="Align Right"').should("be.visible");
	});
});
