context("Workspace Blocks", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.setup_workflow");
			});
	});

	it("Create Test Page", () => {
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.doctype.workspace.workspace.new_page",
		}).as("new_page");

		cy.visit("/app/website");
		cy.get(".codex-editor__redactor .ce-block");
		cy.get('.custom-actions button[data-label="Create%20Workspace"]').click();
		cy.fill_field("title", "Test Block Page", "Data");
		cy.fill_field("icon", "edit", "Icon");
		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in private section
		cy.get('.sidebar-item-container[item-name="Test Block Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Block Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it("Quick List Block", () => {
		cy.create_records([
			{
				doctype: "ToDo",
				description: "Quick List ToDo 1",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 2",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 3",
				status: "Open",
			},
			{
				doctype: "ToDo",
				description: "Quick List ToDo 4",
				status: "Open",
			},
		]);

		cy.intercept({
			method: "GET",
			url: "api/method/frappe.desk.form.load.getdoctype?**",
		}).as("get_doctype");

		cy.visit("/app/tools");
		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".standard-actions .btn-secondary[data-label=Edit]").click();

		// test quick list creation
		cy.get(".ce-block").first().click({ force: true }).type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Quick List").click();

		cy.get_open_dialog().find(".modal-header").click();

		cy.fill_field("document_type", "ToDo", "Link").blur();
		cy.fill_field("label", "ToDo", "Data").blur();
		cy.wait("@get_doctype");

		cy.get_open_dialog().find(".filter-edit-area").should("contain", "No filters selected");
		cy.get_open_dialog().find(".filter-area .add-filter").click();

		cy.get_open_dialog()
			.find(".fieldname-select-area input")
			.type("Workflow State{enter}")
			.blur();
		cy.get_open_dialog().find(".filter-field .input-with-feedback").type("Pending");

		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();

		cy.get(".codex-editor__redactor .ce-block");

		cy.get(".ce-block .quick-list-widget-box").first().as("todo-quick-list");

		cy.get("@todo-quick-list").find(".quick-list-item .status").should("contain", "Pending");

		// test quick-list-item
		cy.get("@todo-quick-list")
			.find(".quick-list-item .title")
			.first()
			.invoke("attr", "title")
			.then((title) => {
				cy.get("@todo-quick-list").find(".quick-list-item").contains(title).click();
				cy.get_field("description", "Text Editor").should("contain", title);
				cy.click_action_button("Approve");
			});
		cy.go("back");

		// test filter-list
		cy.get("@todo-quick-list").realHover().find(".widget-control .filter-list").click();

		cy.get_open_dialog()
			.find(".filter-field .input-with-feedback")
			.type("{selectall}Approved");
		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		cy.get("@todo-quick-list").find(".quick-list-item .status").should("contain", "Approved");

		// test refresh-list
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.reportview.get",
		}).as("refresh-list");

		cy.get("@todo-quick-list").realHover().find(".widget-control .refresh-list").click();
		cy.wait("@refresh-list");

		// test add-new
		cy.get("@todo-quick-list").realHover().find(".widget-control .add-new").click();
		cy.url().should("include", `/todo/new-todo-1`);
		cy.go("back");

		// test see-all
		cy.get("@todo-quick-list").find(".widget-footer .see-all").click();
		cy.open_list_filter();
		cy.get('.filter-field input[data-fieldname="workflow_state"]')
			.invoke("val")
			.should("eq", "Pending");
		cy.go("back");
	});
});
