context("Request Headers Hook", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
	});

	it("injects custom headers via frappe.request.get_headers", () => {
		cy.intercept("POST", "**/api/method/frappe.client.get_list").as("get_list");
		let base_get_headers;

		cy.window().then((win) => {
			base_get_headers = win.frappe.request.get_headers;
			win.frappe.request.get_headers = (opts) => {
				const headers = base_get_headers(opts);
				if (opts?.args?.doctype === "ToDo") headers["X-Test-Header-Hook"] = "enabled";
				return headers;
			};

			win.frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "ToDo",
					fields: ["name"],
					limit_page_length: 1,
				},
			});
		});

		cy.wait("@get_list")
			.its("request.headers")
			.then((headers) => {
				expect(headers["x-test-header-hook"]).to.eq("enabled");
				expect(headers["x-frappe-doctype"]).to.eq("ToDo");
			});

		cy.window().then((win) => {
			win.frappe.request.get_headers = base_get_headers;
		});
	});
});
