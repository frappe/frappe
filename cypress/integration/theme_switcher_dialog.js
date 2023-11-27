context("Theme Switcher Shortcut", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});
	beforeEach(() => {
		cy.reload();
	});
	it("Check Toggle", () => {
		cy.open_theme_dialog();
		cy.get(".modal-backdrop").should("exist");
		cy.findByText("Timeless Night").click();
		cy.get("html").should("have.attr", "data-theme-mode", "dark");
	});
});

Cypress.Commands.add("open_theme_dialog", () => {
	cy.get("body").type("{ctrl+shift+g}");
});
