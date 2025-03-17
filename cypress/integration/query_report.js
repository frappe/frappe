context("Query Report", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
		cy.insert_doc(
			"Report",
			{
				report_name: "Test ToDo Report",
				ref_doctype: "ToDo",
				report_type: "Query Report",
				query: "select * from tabToDo",
			},
			true
		).as("doc");
		cy.create_records({
			doctype: "ToDo",
			description: "this is a test todo for query report",
		}).as("todos");
	});

	it("add custom column in report", () => {
		cy.visit("/app/query-report/Permitted Documents For User");

		cy.get(".page-form.flex", { timeout: 60000 })
			.should("have.length", 1)
			.then(() => {
				cy.get('#page-query-report input[data-fieldname="user"]').as("input-user");
				cy.get("@input-user").focus().type("test@erpnext.com", { delay: 100 }).blur();
				cy.wait(300);
				cy.get('#page-query-report input[data-fieldname="doctype"]').as("input-role");
				cy.get("@input-role").focus().type("Role", { delay: 100 }).blur();

				cy.get(".datatable").should("exist");
				cy.get("#page-query-report .page-actions .menu-btn-group button").click({
					force: true,
				});
				cy.get("#page-query-report .menu-btn-group .dropdown-menu")
					.contains("Add Column")
					.click({ force: true });
				cy.get_open_dialog().get(".modal-title").should("contain", "Add Column");
				cy.get('select[data-fieldname="doctype"]').select("Role (Name)", { force: true });
				cy.get('select[data-fieldname="field"]').select("Role Name", { force: true });
				cy.get('select[data-fieldname="insert_after"]').select("Name", { force: true });
				cy.get_open_dialog()
					.findByRole("button", { name: "Submit" })
					.click({ force: true });
				cy.get("#page-query-report .page-actions .menu-btn-group button").click({
					force: true,
				});
				cy.get("#page-query-report .menu-btn-group .dropdown-menu")
					.contains("Save")
					.click({ timeout: 100, force: true });
				cy.get_open_dialog().get(".modal-title").should("contain", "Save Report");

				cy.get('input[data-fieldname="report_name"]').type("Test Report", {
					delay: 100,
					force: true,
				});
				cy.get_open_dialog()
					.findByRole("button", { name: "Submit" })
					.click({ timeout: 1000, force: true });
			});
	});

	let save_report_and_open = (report, update_name) => {
		cy.get("#page-query-report .page-actions .menu-btn-group button").click({ force: true });
		cy.get("#page-query-report .menu-btn-group .dropdown-menu")
			.contains("Save")
			.click({ timeout: 100, force: true });
		cy.get_open_dialog().get(".modal-title").should("contain", "Save Report");

		cy.get('input[data-fieldname="report_name"]').type(update_name, {
			delay: 100,
			force: true,
		});
		cy.get_open_dialog()
			.findByRole("button", { name: "Submit" })
			.click({ timeout: 1000, force: true });

		cy.visit("/app/query-report/" + report);
		cy.get(".datatable").should("exist");
	};

	it("test multi level query report", () => {
		cy.visit("/app/query-report/Test ToDo Report");
		cy.get(".datatable").should("exist");

		save_report_and_open("Test ToDo Report 1", " 1");
		save_report_and_open("Test ToDo Report 11", "1");
	});
});
