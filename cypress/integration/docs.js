context("Documentation Browser", () => {
	before(() => {
		cy.login();
	});

	it("opens the docs page and loads the first accessible page", () => {
		cy.visit("/desk/docs");
		cy.get(".docs-tree .docs-tree-node").should("have.length.at.least", 1);
		cy.get(".docs-reading-pane").should("not.have.class", "hide");
		cy.get(".docs-reading-pane").should("contain", "Frappe Framework");
	});

	it("navigates nested documentation routes", () => {
		cy.visit("/desk/docs/framework/docs/authoring");
		cy.get('.docs-tree-node.active[data-path="framework/docs/authoring"]').should("exist");
		cy.get(".docs-reading-pane").contains("Authoring Guide");
		cy.get(".navbar-breadcrumbs li").first().should("contain", "Documentation");
		cy.get(".navbar-breadcrumbs li").last().should("contain", "Authoring Guide");
	});

	it("shows not-found state for missing pages", () => {
		cy.visit("/desk/docs/does-not-exist-page");
		cy.get(".docs-state").should("not.have.class", "hide");
		cy.get(".docs-reading-pane").should("have.class", "hide");
		cy.get(".docs-state-content").should("contain", "could not find");
	});
});
