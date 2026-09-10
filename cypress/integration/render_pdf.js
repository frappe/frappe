context("Render PDF", () => {
	const pdf_route = "/api/method/frappe.utils.print_format.report_to_pdf";

	const render_pdf = () =>
		cy
			.window()
			.its("frappe")
			.then((frappe) =>
				frappe.render_pdf("<h1>Stock Balance</h1>", { report_name: "stock_balance.pdf" })
			);

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/app/todo");
	});

	it("freezes the page while the PDF is generated", () => {
		cy.intercept("POST", pdf_route, { statusCode: 504, body: "", delay: 1000 }).as("pdf");

		render_pdf();

		cy.get("#freeze .freeze-message").should("contain", "Generating PDF...");
		cy.wait("@pdf");
		cy.get("#freeze").should("not.exist");
	});

	it("reports a gateway timeout as a size problem", () => {
		cy.intercept("POST", pdf_route, { statusCode: 504, body: "" }).as("pdf");

		render_pdf();
		cy.wait("@pdf");

		cy.get(".msgprint-dialog .modal-title").should("contain", "Could not generate PDF");
		cy.get(".msgprint").should("contain", "may be too large");
	});

	it("points at the Error Log when the server fails for another reason", () => {
		cy.intercept("POST", pdf_route, { statusCode: 500, body: "" }).as("pdf");

		render_pdf();
		cy.wait("@pdf");

		cy.get(".msgprint").should("contain", "Check the Error Log for details.");
	});

	it("shows the server message when the response carries one", () => {
		cy.intercept("POST", pdf_route, {
			statusCode: 417,
			body: {
				_server_messages: JSON.stringify([
					JSON.stringify({ message: "Report is too large to render" }),
				]),
			},
		}).as("pdf");

		render_pdf();
		cy.wait("@pdf");

		cy.get(".msgprint").should("contain", "Report is too large to render");
	});

	it("does not blame report size when the connection drops", () => {
		cy.intercept("POST", pdf_route, { forceNetworkError: true }).as("pdf");

		render_pdf();

		cy.get(".msgprint").should("contain", "Check your connection");
		cy.get("#freeze").should("not.exist");
	});
});
