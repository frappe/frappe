context("Dashboard Chart", () => {
	before(() => {
		cy.login();
		cy.visit("/desk/website");
	});

	it("Check filter populate for child table doctype", () => {
		cy.new_form("Dashboard Chart");
		cy.get('[data-fieldname="parent_document_type"]').should("have.css", "display", "none");

		cy.get_field("chart_name", "Data").should("be.visible");
		cy.fill_field("chart_name", "Test Chart", "Data");
		cy.fill_field("document_type", "Workspace Link", "Link");

		// wait for link field events to complete
		cy.wait(1000);

		cy.get('[data-fieldname="filters_json"]').click();
		cy.get(".modal-dialog", { timeout: 500 }).should("be.visible");

		cy.get(".modal-body .filter-action-buttons .add-filter").click();
		cy.get(".modal-body .fieldname-select-area").click();
		cy.get(".modal-actions .btn-modal-close").click();
	});
});
