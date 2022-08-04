context("Theme Switcher Shortcut", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});
	beforeEach(() => {
		cy.reload();
	});
	it("Check Toggle", () => {
		cy.open_theme_dialog("{ctrl+shift+g}");
		cy.get(".modal-backdrop").should("exist");
		cy.get(".theme-grid > div").first().click();
		cy.close_theme("{ctrl+shift+g}");
		cy.get(".modal-backdrop").should("not.exist");
	});
	it("Check Enter", () => {
		cy.open_theme_dialog("{ctrl+shift+g}");
		cy.get(".theme-grid > div").first().click();
		cy.close_theme("{enter}");
		cy.get(".modal-backdrop").should("not.exist");
	});
});

Cypress.Commands.add("open_theme_dialog", (shortcut_keys) => {
	cy.get("body").type(shortcut_keys);
});
Cypress.Commands.add("close_theme", (shortcut_keys) => {
	cy.get(".modal-header").type(shortcut_keys);
});
