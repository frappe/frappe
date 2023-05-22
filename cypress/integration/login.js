context("Login", () => {
	beforeEach(() => {
		cy.request("/api/method/logout");
		cy.visit("/login");
		cy.location("pathname").should("eq", "/login");
	});

	it("greets with login screen", () => {
		cy.get(".page-card-head").contains("Login");
	});

	it("validates password", () => {
		cy.get("#login_email").type("Administrator");
		cy.findByRole("button", { name: "Login" }).click();
		cy.location("pathname").should("eq", "/login");
	});

	it("validates email", () => {
		cy.get("#login_password").type("qwe");
		cy.findByRole("button", { name: "Login" }).click();
		cy.location("pathname").should("eq", "/login");
	});

	it("shows invalid login if incorrect credentials", () => {
		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type("qwer");

		cy.findByRole("button", { name: "Login" }).click();
		cy.findByRole("button", { name: "Invalid Login. Try again." }).should("exist");
		cy.location("pathname").should("eq", "/login");
	});

	it("logs in using correct credentials", () => {
		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type(Cypress.env("adminPassword"));

		cy.findByRole("button", { name: "Login" }).click();
		cy.location("pathname").should("eq", "/app");
		cy.window().its("frappe.session.user").should("eq", "Administrator");
	});

	it("check redirect after login", () => {
		// mock for OAuth 2.0 client_id, redirect_uri, scope and state
		const payload = new URLSearchParams({
			uuid: "6fed1519-cfd8-4a2d-84a6-9a1799c7c741",
			encoded_string: "hello all",
			encoded_url: "http://test.localhost/callback",
			base64_string: "aGVsbG8gYWxs",
		});

		cy.request("/api/method/logout");

		// redirect-to /me page with params to mock OAuth 2.0 like request
		cy.visit(
			"/login?redirect-to=/me?" + encodeURIComponent(payload.toString().replace("+", " "))
		);

		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type(Cypress.env("adminPassword"));

		cy.findByRole("button", { name: "Login" }).click();

		// verify redirected location and url params after login
		cy.url().should("include", "/me?" + payload.toString().replace("+", "%20"));
	});
});
