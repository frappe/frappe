context("Form", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.call("frappe.tests.ui_test_helpers.create_contact_records");
			});
	});

	it("create a new form", () => {
		cy.visit("/app/todo/new");
		cy.get_field("description", "Text Editor")
			.type("this is a test todo", { force: true })
			.wait(200);
		cy.get(".page-title").should("contain", "Not Saved");
		cy.intercept({
			method: "POST",
			url: "api/method/frappe.desk.form.save.savedocs",
		}).as("form_save");
		cy.get(".primary-action").click();
		cy.wait("@form_save").its("response.statusCode").should("eq", 200);

		cy.go_to_list("ToDo");
		cy.clear_filters();
		cy.get(".page-head").findByTitle("To Do").should("exist");
		cy.get(".list-row").should("contain", "this is a test todo");
	});

	it("navigates between documents with child table list filters applied", () => {
		cy.visit("/app/contact");

		cy.clear_filters();
		cy.get('.standard-filter-section [data-fieldname="name"] input')
			.type("Test Form Contact 3")
			.blur();
		cy.click_listview_row_item_with_text("Test Form Contact 3");

		cy.get("#page-Contact .page-head").findByTitle("Test Form Contact 3").should("exist");
		cy.get(".prev-doc").should("be.visible").click();
		cy.get(".msgprint-dialog .modal-body").contains("No further records").should("be.visible");
		cy.hide_dialog();

		cy.get("#page-Contact .page-head").findByTitle("Test Form Contact 3").should("exist");
		cy.get(".next-doc").should("be.visible").click();
		cy.get(".msgprint-dialog .modal-body").contains("No further records").should("be.visible");
		cy.hide_dialog();

		cy.get("#page-Contact .page-head").findByTitle("Test Form Contact 3").should("exist");

		// clear filters
		cy.visit("/app/contact");
		cy.clear_filters();
	});

	it("validates behaviour of Data options validations in child table", () => {
		// test email validations for set_invalid controller
		let website_input = "website.in";
		let valid_email = "user@email.com";
		let expectBackgroundColor = "rgb(255, 245, 245)";

		cy.visit("/app/contact/new");
		cy.get('.frappe-control[data-fieldname="email_ids"]').as("table");
		cy.get("@table").find("button.grid-add-row").click();
		cy.get("@table").find("button.grid-add-row").click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@table").find('[data-idx="2"]').as("row2");
		cy.get("@row1").click();
		cy.get("@row1").find("input.input-with-feedback.form-control").as("email_input1");

		cy.get("@email_input1").type(website_input, { waitForAnimations: false });
		cy.fill_field("company_name", "Test Company");

		cy.get("@row2").click();
		cy.get("@row2").find("input.input-with-feedback.form-control").as("email_input2");
		cy.get("@email_input2").type(valid_email, { waitForAnimations: false });

		cy.get("@row1").click();
		cy.get("@email_input1").should(($div) => {
			const style = window.getComputedStyle($div[0]);
			expect(style.backgroundColor).to.equal(expectBackgroundColor);
		});
		cy.get("@email_input1").should("have.class", "invalid");

		cy.get("@row2").click();
		cy.get("@email_input2").should("not.have.class", "invalid");
	});

	it("Shows version conflict warning", { scrollBehavior: false }, () => {
		cy.visit("/app/todo");

		cy.insert_doc("ToDo", { description: "old" }).then((doc) => {
			cy.visit(`/app/todo/${doc.name}`);
			// make form dirty
			cy.fill_field("status", "Cancelled", "Select");

			// update doc using api - simulating parallel change by another user
			cy.update_doc("ToDo", doc.name, { status: "Closed" }).then(() => {
				cy.findByRole("button", { name: "Refresh" }).click();
				cy.get_field("status", "Select").should("have.value", "Closed");
			});
		});
	});

	it("let user undo/redo field value changes", { scrollBehavior: false }, () => {
		const jump_to_field = (field_label) => {
			cy.get("body")
				.type("{esc}") // lose focus if any
				.type("{ctrl+j}") // jump to field
				.type(field_label)
				.wait(500)
				.type("{enter}")
				.wait(200)
				.type("{enter}")
				.wait(500);
		};

		const type_value = (value) => {
			cy.focused().clear().type(value).type("{esc}");
		};

		const undo = () => cy.get("body").type("{esc}").type("{ctrl+z}").wait(500);
		const redo = () => cy.get("body").type("{esc}").type("{ctrl+y}").wait(500);

		cy.new_form("User");

		jump_to_field("Email");
		type_value("admin@example.com");

		jump_to_field("Username");
		type_value("admin42");

		jump_to_field("Send Welcome Email");
		cy.focused().uncheck();

		// make a mistake
		jump_to_field("Username");
		type_value("admin24");

		// undo behaviour
		undo();
		cy.get_field("username").should("have.value", "admin42");

		// redo behaviour
		redo();
		cy.get_field("username").should("have.value", "admin24");

		// undo everything & redo everything, ensure same values at the end
		undo();
		undo();
		undo();
		undo();
		redo();
		redo();
		redo();
		redo();

		cy.compare_document({
			username: "admin24",
			email: "admin@example.com",
			send_welcome_email: 0,
		});
	});
});
