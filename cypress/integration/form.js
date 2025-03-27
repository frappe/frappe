const jump_to_field = (field_label) => {
	cy.get("body")
		.type("{esc}") // lose focus if any
		.type("{ctrl+j}") // jump to field
		.type(field_label)
		.wait(500)
		.type("{enter}")
		.wait(200)
		.type("{enter}")
		.wait(1000);
};

const type_value = (value) => {
	cy.focused().clear().type(value).type("{esc}");
};

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

	beforeEach(() => {
		cy.login();
		cy.visit("/app/website");
	});

	it("create a new form", () => {
		cy.visit("/app/todo/new");
		cy.get_field("description", "Text Editor")
			.type("this is a test todo", { force: true })
			.wait(1000);
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
		cy.fill_field("company_name", "Test Company");

		cy.get('.frappe-control[data-fieldname="email_ids"]').as("table");
		cy.get("@table").find("button.grid-add-row").click();
		cy.get("@table").find("button.grid-add-row").click();
		cy.get("@table").find('[data-idx="1"]').as("row1");
		cy.get("@table").find('[data-idx="2"]').as("row2");
		cy.get("@row1").click();
		cy.get("@row1").find("input.input-with-feedback.form-control").as("email_input1");

		cy.get("@email_input1").type(website_input, { waitForAnimations: false });

		cy.get("@row2").click();
		cy.get("@row2").find("input.input-with-feedback.form-control").as("email_input2");
		cy.get("@email_input2").type(valid_email, { waitForAnimations: false });

		cy.get("@row1").click();
		cy.get("@email_input1").should("have.class", "invalid");

		cy.get("@row2").click();
		cy.get("@email_input2").should("not.have.class", "invalid");
	});

	it("Jump to field in collapsed section", { scrollBehavior: false }, () => {
		cy.new_form("User");

		jump_to_field("Location"); // this is in collapsed section
		type_value("Bermuda");

		cy.get_field("location").should("have.value", "Bermuda");
	});

	it("update docfield property using set_df_property in child table", () => {
		cy.visit("/app/contact/Test Form Contact 1");
		cy.window()
			.its("cur_frm")
			.then((frm) => {
				cy.get('.frappe-control[data-fieldname="phone_nos"]').as("table");

				// set property before form_render event of child table
				cy.get("@table")
					.find('[data-idx="1"]')
					.invoke("attr", "data-name")
					.then((cdn) => {
						frm.set_df_property(
							"phone_nos",
							"hidden",
							1,
							"Contact Phone",
							"is_primary_phone",
							cdn
						);
					});

				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_phone"]')
					.should("be.hidden");
				cy.get("@table-form").find(".grid-footer-toolbar").click();

				// set property on form_render event of child table
				cy.get("@table").find('[data-idx="1"] .btn-open-row').click();
				cy.get("@table")
					.find('[data-idx="1"]')
					.invoke("attr", "data-name")
					.then((cdn) => {
						frm.set_df_property(
							"phone_nos",
							"hidden",
							0,
							"Contact Phone",
							"is_primary_phone",
							cdn
						);
					});

				cy.get(".grid-row-open").as("table-form");
				cy.get("@table-form")
					.find('.frappe-control[data-fieldname="is_primary_phone"]')
					.should("be.visible");
				cy.get("@table-form").find(".grid-footer-toolbar").click();
			});
	});
});
