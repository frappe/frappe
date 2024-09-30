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
		cy.get(".btn-new-workspace").click();
		cy.fill_field("title", "Test Block Page", "Data");
		cy.fill_field("type", "Workspace", "Select");
		cy.get_open_dialog().find(".modal-header").click();
		cy.get_open_dialog().find(".btn-primary").click();

		// check if sidebar item is added in private section
		cy.get('.sidebar-item-container[item-title="Test Block Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);
		cy.wait(300);
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-title="Test Block Page"]').should(
			"have.attr",
			"item-public",
			"0"
		);

		cy.wait("@new_page");
	});

	it.skip("Quick List Block", () => {
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

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".btn-edit-workspace").click();

		// test quick list creation
		cy.get(".ce-block").first().click({ force: true }).type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Quick List").click();

		cy.fill_field("label", "ToDo", "Data");
		cy.fill_field("document_type", "ToDo", "Link").blur();
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
			.focus()
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

	it("Number Card Block", () => {
		cy.create_records([
			{
				doctype: "Number Card",
				label: "Test Number Card",
				document_type: "ToDo",
				color: "#f74343",
			},
		]);

		cy.get(".codex-editor__redactor .ce-block");
		cy.get(".btn-edit-workspace").click();

		cy.get(".ce-block").first().click({ force: true }).type("{enter}");
		cy.get(".block-list-container .block-list-item").contains("Number Card").click();

		// add number card
		cy.fill_field("number_card_name", "Test Number Card", "Link");
		cy.get('[data-fieldname="number_card_name"] ul div').contains("Test Number Card").click();
		cy.click_modal_primary_button("Add");
		cy.get(".ce-block .number-widget-box").first().as("number_card");
		cy.get("@number_card").find(".widget-title").should("contain", "Test Number Card");
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.get("@number_card").find(".widget-title").should("contain", "Test Number Card");

		// edit number card
		cy.get(".btn-edit-workspace").click();
		cy.get("@number_card").realHover().find(".widget-control .edit-button").click();
		cy.get_field("label", "Data").invoke("val", "ToDo Count");
		cy.click_modal_primary_button("Save");
		cy.get("@number_card").find(".widget-title").should("contain", "ToDo Count");
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.get("@number_card").find(".widget-title").should("contain", "ToDo Count");
	});
});
