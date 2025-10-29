context("Workspace 2.0", () => {
	before(() => {
		cy.visit("/login");
		cy.login();
	});

	it("Navigate to page from sidebar", () => {
		cy.visit("/app/build");
		cy.get(".codex-editor__redactor .ce-block");
		cy.get('.sidebar-item-container[item-title="Website"]').first().click();
		cy.location("pathname").should("eq", "/app/website");
	});

	it("Create Private Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.new_page",
		}).as("new_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".btn-new-workspace").click();
		cy.fill_field("title", "Test Private Page", "Data");
		cy.fill_field("type", "Workspace", "Select");
		cy.wait(300);

		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in pubic section
		cy.get('.sidebar-item-container[item-title="Test Private Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);
		cy.wait(300);
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-title="Test Private Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it("Create Child Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.new_page",
		}).as("new_page");

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".btn-new-workspace").click();
		cy.fill_field("title", "Test Child Page", "Data");
		cy.fill_field("parent", "Test Private Page", "Select");
		cy.fill_field("type", "Workspace", "Select");
		cy.get_open_dialog().find(".modal-header").click();
		cy.wait(300);
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in pubic section
		cy.get('.sidebar-item-container[item-title="Test Child Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);
		cy.wait(300);
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-title="Test Child Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it("Add New Block", () => {
		cy.get('.sidebar-item-container[item-title="Test Private Page"]').as("sidebar-item");

		cy.get("@sidebar-item").find(".standard-sidebar-item").first().click({ force: true });

		cy.get(".btn-edit-workspace").click({ force: true });

		cy.get(".ce-block").click().type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Heading").click();
		cy.get(":focus").type("Header");
		cy.get(".ce-block:last").find(".ce-header").should("exist");

		cy.get(".ce-block:last").click().type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Text").click();
		cy.get(":focus").type("Paragraph text");
		cy.get(".ce-block:last").find(".ce-paragraph").should("exist");
	});

	it("Delete A Block", () => {
		cy.get(":focus").click();
		cy.get(".paragraph-control .setting-btn").click();
		cy.get(".paragraph-control .dropdown-item").contains("Delete").click();
		cy.get(".ce-block:last").find(".ce-paragraph").should("not.exist");
	});

	it("Shrink and Expand A Block", () => {
		cy.get(":focus").click();
		cy.get(".ce-block:last .setting-btn").click();
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-11");
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-10");
		cy.get(".ce-block:last .dropdown-item").contains("Shrink").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-9");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-10");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-11");
		cy.get(".ce-block:last .dropdown-item").contains("Expand").click();
		cy.get(".ce-block:last").should("have.class", "col-xs-12");
		cy.wait(300);
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
	});
});
