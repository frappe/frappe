context("Awesome Bar", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
		cy.visit("/app/todo"); // Make sure ToDo filters are cleared.
		cy.clear_filters();
		cy.visit("/app/blog-post"); // Make sure Blog Post filters are cleared.
		cy.clear_filters();
		cy.visit("/app/website"); // Go to some other page.
	});

	beforeEach(() => {
		cy.get(".navbar .navbar-home").click();
		cy.findByPlaceholderText("Search or type a command (Ctrl + G)").as("awesome_bar");
		cy.get("@awesome_bar").type("{selectall}");
	});

	after(() => {
		cy.visit("/app/todo"); // Make sure we're not bleeding any filters to the next spec.
		cy.clear_filters();
	});

	it("navigates to doctype list", () => {
		// Entering singular to see if 'List' option comes first and 'New' option is present.
		cy.get("@awesome_bar").type("todo");
		cy.wait(100); // Wait a bit before hitting enter.
		cy.get(".awesomplete").findByRole("listbox").should("be.visible");
		cy.get('ul[id="awesomplete_list_1"] li').first().contains("ToDo List");
		cy.get('ul[id="awesomplete_list_1"] li').contains("New ToDo");
		// Add plural "s" to see if 'List' still comes first, while 'New' is gone.
		cy.get("@awesome_bar").type("s");
		cy.wait(100);
		cy.get('ul[id="awesomplete_list_1"] li').first().contains("ToDos List");
		cy.get('ul[id="awesomplete_list_1"] li').contains("New ToDo").should("not.exist");
		// Now hit enter to open the ToDo List and see if it's there.
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.location("pathname").should("eq", "/app/todo");
	});

	it("finds text in doctype list", () => {
		cy.get("@awesome_bar").type("test in todo");
		cy.wait(150); // Wait a bit before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "To Do");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.get('[data-original-title="ID"] > input').should("have.value", "%test%");
	});

	it("filter preserved, now finds something else", () => {
		cy.visit("/app/todo");
		cy.get(".title-text").should("contain", "To Do");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.get('[data-original-title="ID"] > input').as("filter");
		cy.get("@filter").should("have.value", "%test%");
		cy.get("@awesome_bar").type("anothertest in todo");
		cy.wait(200); // Wait a bit longer before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.get("@filter").should("have.value", "%anothertest%");
	});

	it("navigates to another doctype, filter not bleeding", () => {
		cy.get("@awesome_bar").type("blog post");
		cy.wait(150); // Wait a bit before hitting enter.
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text").should("contain", "Blog Post");
		cy.wait(200); // Wait a bit longer before checking the filter.
		cy.location("search").should("be.empty");
	});

	it("navigates to new form", () => {
		cy.get("@awesome_bar").type("new blog post");
		cy.wait(150); // Wait a bit before hitting enter
		cy.get("@awesome_bar").type("{enter}");
		cy.get(".title-text:visible").should("have.text", "New Blog Post");
	});

	it("calculates math expressions", () => {
		cy.get("@awesome_bar").type("55 + 32");
		cy.wait(150); // Wait a bit before hitting enter
		cy.get("@awesome_bar").type("{downarrow}{enter}");
		cy.get(".modal-title").should("contain", "Result");
		cy.get(".msgprint").should("contain", "55 + 32 = 87");
	});
});
