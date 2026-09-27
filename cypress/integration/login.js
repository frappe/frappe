context("Login", () => {
	beforeEach(() => {
		cy.visit("/");
		cy.call("logout");
		cy.visit("/login");
		cy.location("pathname").should("eq", "/login");
	});

	it("greets with login screen", () => {
		cy.get(".page-card-head").contains("Sign In");
	});

	it("validates password", () => {
		cy.get("#login_email").type("Administrator");
		cy.findByRole("button", { name: "Continue" }).click();
		cy.location("pathname").should("eq", "/login");
	});

	it("validates email", () => {
		cy.get("#login_password").type("qwe");
		cy.findByRole("button", { name: "Continue" }).click();
		cy.location("pathname").should("eq", "/login");
	});

	it("shows invalid login if incorrect credentials", () => {
		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type("qwer");

		cy.findByRole("button", { name: "Continue" }).click();
		cy.get(".login-error-banner")
			.should("be.visible")
			.contains("Invalid credentials, try again.");
		cy.location("pathname").should("eq", "/login");
	});

	it("logs in using correct credentials", () => {
		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type(Cypress.env("adminPassword"));

		cy.findByRole("button", { name: "Continue" }).click();
		cy.location("pathname").should("match", /^\/desk/);
		cy.window().its("frappe.session.user").should("eq", "Administrator");
	});

	it("includes redirect-to when requesting an email login link", () => {
		const redirect_to =
			"/api/method/frappe.integrations.oauth2.authorize?client_id=test-client&scope=openid%20all&state=a%2Bb%3D";
		const query = new URLSearchParams({ "redirect-to": redirect_to });
		cy.visit(`/login?${query}#login-with-email-link`);
		cy.window().then((win) => {
			cy.stub(win.login, "call").resolves().as("sendLoginLink");
		});

		cy.get("#login_with_email_link_email").type("email-link@example.com");
		cy.get(".form-login-with-email-link").submit();

		cy.get("@sendLoginLink").should("have.been.calledWithMatch", {
			cmd: "frappe.www.login.send_login_link",
			email: "email-link@example.com",
			redirect_to,
		});
	});

	it("check redirect after login", () => {
		// mock for OAuth 2.0 client_id, redirect_uri, scope and state
		const payload = new URLSearchParams({
			uuid: "6fed1519-cfd8-4a2d-84a6-9a1799c7c741",
			encoded_string: "hello all",
			encoded_url: "http://test.localhost/callback",
			base64_string: "aGVsbG8gYWxs",
		});

		cy.call("logout");

		// redirect-to /me page with params to mock OAuth 2.0 like request
		cy.visit(
			"/login?redirect-to=/me?" + encodeURIComponent(payload.toString().replace("+", " "))
		);

		cy.get("#login_email").type("Administrator");
		cy.get("#login_password").type(Cypress.env("adminPassword"));

		cy.findByRole("button", { name: "Continue" }).click();

		// verify redirected location and url params after login
		cy.url().should("include", "/me?" + payload.toString().replace("+", "%20"));
	});
});
