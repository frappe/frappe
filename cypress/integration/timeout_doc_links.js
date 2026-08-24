context("Timeout error popups", () => {
	before(() => {
		cy.login();
	});

	it("links to the documentation on a gateway timeout", () => {
		cy.visit("/app/todo");
		cy.intercept("POST", "/api/method/frappe.client.get_count", {
			statusCode: 504,
			body: {},
		}).as("timed_out");

		cy.window()
			.its("frappe")
			.then((frappe) => frappe.call("frappe.client.get_count", { doctype: "ToDo" }));
		cy.wait("@timed_out");

		cy.get(".modal-title").should("contain", "Request Timed Out");
		cy.get(".msgprint")
			.find("a")
			.should("have.attr", "href")
			.and(
				"include",
				"docs.frappe.io/cloud/private-benches/common-issues/request-timed-out"
			);
	});

	it("links to the documentation when a query times out", () => {
		cy.visit("/app/todo");
		cy.intercept("POST", "/api/method/frappe.client.get_count", {
			statusCode: 500,
			body: { exception: "frappe.exceptions.QueryTimeoutError: Query timed out" },
		}).as("query_timed_out");

		cy.window()
			.its("frappe")
			.then((frappe) => frappe.call("frappe.client.get_count", { doctype: "ToDo" }));
		cy.wait("@query_timed_out");

		cy.get(".modal-title").should("contain", "Request Timeout");
		cy.get(".msgprint").should("contain", "Server was too busy");
		cy.get(".msgprint")
			.find("a")
			.should("have.attr", "href")
			.and("include", "request-timeout-server-was-too-busy-to-process-this-request");
	});
});
