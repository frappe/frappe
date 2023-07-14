const path = require("path");

function check_downloaded_file(filename) {
	const downloads = Cypress.config("downloadsFolder");
	cy.readFile(path.join(downloads, filename), "base64").then((content) => {
		expect(content.length).to.be.above(1);
	});

	cy.window().then((win) => {
		expect(win.console.error).to.have.callCount(0);
	});
}

const TEST_TODO = "this is a test todo for query report export";

context("PDF Prints", () => {
	before(() => {
		cy.login();
		cy.visit("/app/query-report/ToDo");

		cy.create_records({
			doctype: "ToDo",
			description: TEST_TODO,
		});
	});

	beforeEach(() => {
		cy.visit("/app/query-report/ToDo");
		cy.contains(TEST_TODO).should("be.visible"); // wait for report to load
	});

	it("Render print view of report", () => {
		cy.click_menu_button("Print");
		cy.window().then((win) => {
			cy.stub(win, "open", () => {
				return { document: win.document.implementation.createHTMLDocument() };
			}).as("window_open");

			cy.click_modal_primary_button("Submit");
			cy.get("@window_open").should("be.called");
		});
	});

	// doesn't work in headless mode
	it.skip("Render PDF of report", () => {
		cy.click_menu_button("PDF");
		cy.click_modal_primary_button("Submit");

		check_downloaded_file("ToDo.pdf");
	});
});
