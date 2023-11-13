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
		cy.intercept("POST", "/api/method/frappe.core.doctype.user.user.switch_theme").as(
			"set_theme"
		);
		cy.findByText("Timeless Night").click();
		cy.wait("@set_theme");
		cy.get("html").should("have.attr", "data-theme-mode", "dark");
		cy.close_theme("{ctrl+shift+g}");
		cy.wait(400); // wait for modal to close
		cy.get(".modal-backdrop").should("not.exist");
	});
	it("Check Enter", () => {
		cy.open_theme_dialog();
		cy.intercept("POST", "/api/method/frappe.core.doctype.user.user.switch_theme").as(
			"set_theme"
		);
		cy.findByText("Frappe Light").click();
		cy.wait("@set_theme");
		cy.get("html").should("have.attr", "data-theme-mode", "light");
		cy.close_theme("{enter}");
		cy.wait(400); // wait for modal to close
		cy.get(".modal-backdrop").should("not.exist");
	});
});

Cypress.Commands.add("open_theme_dialog", () => {
	cy.get("body").type("{ctrl+shift+g}");
});
Cypress.Commands.add("close_theme", (shortcut_keys) => {
	cy.get(".modal-header").type(shortcut_keys);
});
