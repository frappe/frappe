context("Awesome Bar", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/todo"); // Make sure ToDo filters are cleared.
		cy.clear_filters();
		cy.visit("/app/web-page"); // Make sure Blog Post filters are cleared.
		cy.clear_filters();
		cy.visit("/app/build"); // Go to some other page.
	});

	beforeEach(() => {
		let txt = `Search or type a command (${
			window.navigator.platform === "MacIntel" ? "⌘" : "Ctrl"
		} + K)`;
		cy.findByPlaceholderText(txt).as("awesome_bar");
		cy.get("@awesome_bar").type("{selectall}");
	});

	after(() => {
		cy.visit("/app/todo"); // Make sure we're not bleeding any filters to the next spec.
		cy.clear_filters();
	});

	it("navigates to doctype list", () => {
		cy.get("@awesome_bar").type("todo");
		cy.wait(100); // Wait a bit before hitting enter.
		cy.get(".awesomplete").findByRole("listbox").should("be.visible");
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.location("pathname").should("eq", "/app/todo");
	});

	it("finds text in doctype list", () => {
		cy.get("@awesome_bar").type("test in todo");
		cy.wait(150); // Wait a bit before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.wait(400); // Wait a bit longer before checking the filter.
		cy.get('[data-original-title="ID"]:visible > input').should("have.value", "%test%");

		// filter preserved, now finds something else
		cy.visit("/app/todo");
		cy.get(".title-text").should("contain", "To Do");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.get('[data-original-title="ID"]:visible > input').as("filter");
		cy.get("@filter").should("have.value", "%test%");
		cy.get("@awesome_bar").type("anothertest in todo");
		cy.wait(200); // Wait a bit longer before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.get("@filter").should("have.value", "%anothertest%");
	});

	it("navigates to another doctype, filter not bleeding", () => {
		cy.get("@awesome_bar").type("web page");
		cy.wait(150); // Wait a bit before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "Web Page");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.location("search").should("be.empty");
	});

	it("navigates to new form", () => {
		cy.get("@awesome_bar").type("new web page");
		cy.wait(150); // Wait a bit before hitting enter
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text:visible").should("have.text", "New Web Page");
	});

	it("calculates math expressions", () => {
		cy.get("@awesome_bar").type("55 + 32");
		cy.wait(150); // Wait a bit before hitting enter
		cy.get("@awesome_bar").type("{downarrow}{enter}");
		cy.get(".modal-title").should("contain", "Result");
		cy.get(".msgprint").should("contain", "55 + 32 = 87");
	});
});
