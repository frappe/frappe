context("Awesome Bar", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/website");
	});

	beforeEach(() => {
		cy.get(".navbar .navbar-home").click();
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").as("awesome_bar");
		cy.get("@awesome_bar").type("{selectall}");
	});

	it("navigates to doctype list", () => {
		cy.get("@awesome_bar").type("todo");
		cy.wait(100);
		cy.get(".awesomplete").findByRole("listbox").should("be.visible");
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.location("pathname").should("eq", "/app/todo");
	});

	it("find text in doctype list", () => {
		cy.get("@awesome_bar").type("test in todo");
		cy.wait(100);
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.wait(200);
		const name_filter = cy.get('[data-original-title="ID"] > input');
		name_filter.should("have.value", "%test%");
		cy.clear_filters();
	});

	it("navigates to new form", () => {
		cy.get("@awesome_bar").type("new blog post");
		cy.wait(100);
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text:visible").should("have.text", "New Blog Post");
	});

	it("calculates math expressions", () => {
		cy.get("@awesome_bar").type("55 + 32");
		cy.wait(100);
		cy.get("@awesome_bar").type("{downarrow}{enter}");
		cy.get(".modal-title").should("contain", "Result");
		cy.get(".msgprint").should("contain", "55 + 32 = 87");
	});
});
