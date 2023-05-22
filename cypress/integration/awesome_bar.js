context("Awesome Bar", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/website");
	});

	beforeEach(() => {
		cy.get(".navbar .navbar-home").click();
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").clear();
	});

	it("navigates to doctype list", () => {
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").type("todo", {
			delay: 700,
		});
		cy.get(".awesomplete").findByRole("listbox").should("be.visible");
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").type("{enter}", {
			delay: 700,
		});

		cy.get(".title-text").should("contain", "To Do");

		cy.location("pathname").should("eq", "/app/todo");
	});

	it("find text in doctype list", () => {
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").type(
			"test in todo{enter}",
			{ delay: 700 }
		);

		cy.get(".title-text").should("contain", "To Do");

		cy.findByPlaceholderText("ID").should("have.value", "%test%");
		cy.clear_filters();
	});

	it("navigates to new form", () => {
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").type(
			"new blog post{enter}",
			{ delay: 700 }
		);

		cy.get(".title-text:visible").should("have.text", "New Blog Post");
	});

	it("calculates math expressions", () => {
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").type(
			"55 + 32{downarrow}{enter}",
			{ delay: 700 }
		);

		cy.get(".modal-title").should("contain", "Result");
		cy.get(".msgprint").should("contain", "55 + 32 = 87");
	});
});
