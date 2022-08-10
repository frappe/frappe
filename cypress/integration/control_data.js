context("Data Control", () => {
	before(() => {
		cy.login();
		cy.visit("/app/doctype");
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.xcall("frappe.tests.ui_test_helpers.create_doctype", {
					name: "Test Data Control",
					fields: [
						{
							label: "Name",
							fieldname: "name1",
							fieldtype: "Data",
							options: "Name",
							in_list_view: 1,
							reqd: 1,
						},
						{
							label: "Email-ID",
							fieldname: "email",
							fieldtype: "Data",
							options: "Email",
							in_list_view: 1,
							reqd: 1,
						},
						{
							label: "Phone No.",
							fieldname: "phone",
							fieldtype: "Data",
							options: "Phone",
							in_list_view: 1,
							reqd: 1,
						},
					],
				});
			});
	});

	it("check custom formatters", () => {
		cy.visit(`/app/doctype/User`);
		cy.get(
			'[data-fieldname="fields"] .grid-row[data-idx="2"] [data-fieldname="fieldtype"] .static-area'
		).should("have.text", "Section Break");
	});

	it('Verifying data control by inputting different patterns for "Name" field', () => {
		cy.new_form("Test Data Control");

		//Checking the URL for the new form of the doctype
		cy.location("pathname").should("eq", "/app/test-data-control/new-test-data-control-1");
		cy.get(".title-text").should("have.text", "New Test Data Control");
		cy.get('.frappe-control[data-fieldname="name1"]')
			.find("label")
			.should("have.class", "reqd");
		cy.get('.frappe-control[data-fieldname="email"]')
			.find("label")
			.should("have.class", "reqd");
		cy.get('.frappe-control[data-fieldname="phone"]')
			.find("label")
			.should("have.class", "reqd");

		//Checking if the status is "Not Saved" initially
		cy.get(".indicator-pill").should("have.text", "Not Saved");

		//Inputting data in the field
		cy.fill_field("name1", "@@###", "Data");
		cy.fill_field("email", "test@example.com", "Data");
		cy.fill_field("phone", "9834280031", "Data");

		//Checking if the border color of the field changes to red
		cy.get('.frappe-control[data-fieldname="name1"]').should("have.class", "has-error");
		cy.save();

		//Checking for the error message
		cy.get(".modal-title").should("have.text", "Message");
		cy.get(".msgprint").should("have.text", "@@### is not a valid Name");
		cy.hide_dialog();

		cy.get_field("name1", "Data").clear({ force: true });
		cy.fill_field("name1", "Komal{}/!", "Data");
		cy.get('.frappe-control[data-fieldname="name1"]').should("have.class", "has-error");
		cy.save();
		cy.get(".modal-title").should("have.text", "Message");
		cy.get(".msgprint").should("have.text", "Komal{}/! is not a valid Name");
		cy.hide_dialog();
	});

	it('Verifying data control by inputting different patterns for "Email" field', () => {
		cy.get_field("name1", "Data").clear({ force: true });
		cy.fill_field("name1", "Komal", "Data");
		cy.get_field("email", "Data").clear({ force: true });
		cy.fill_field("email", "komal", "Data");
		cy.get('.frappe-control[data-fieldname="email"]').should("have.class", "has-error");
		cy.save();
		cy.get(".modal-title").should("have.text", "Message");
		cy.get(".msgprint").should("have.text", "komal is not a valid Email Address");
		cy.hide_dialog();
		cy.get_field("email", "Data").clear({ force: true });
		cy.fill_field("email", "komal@test", "Data");
		cy.get('.frappe-control[data-fieldname="email"]').should("have.class", "has-error");
		cy.save();
		cy.get(".modal-title").should("have.text", "Message");
		cy.get(".msgprint").should("have.text", "komal@test is not a valid Email Address");
		cy.hide_dialog();
	});

	it('Verifying data control by inputting different patterns for "Phone" field', () => {
		cy.get_field("email", "Data").clear({ force: true });
		cy.fill_field("email", "komal@test.com", "Data");
		cy.get_field("phone", "Data").clear({ force: true });
		cy.fill_field("phone", "komal", "Data");
		cy.get('.frappe-control[data-fieldname="phone"]').should("have.class", "has-error");
		cy.findByRole("button", { name: "Save" }).click({ force: true });
		cy.get(".modal-title").should("have.text", "Message");
		cy.get(".msgprint").should("have.text", "komal is not a valid Phone Number");
		cy.hide_dialog();
	});

	it("Inputting correct data and saving the doc", () => {
		//Inputting the data as expected and saving the document
		cy.get_field("name1", "Data").clear({ force: true });
		cy.get_field("email", "Data").clear({ force: true });
		cy.get_field("phone", "Data").clear({ force: true });
		cy.fill_field("name1", "Komal", "Data");
		cy.fill_field("email", "komal@test.com", "Data");
		cy.fill_field("phone", "9432380001", "Data");
		cy.findByRole("button", { name: "Save" }).click({ force: true });
		//Checking if the fields contains the data which has been filled in
		cy.location("pathname").should("not.be", "/app/test-data-control/new-test-data-control-1");
		cy.get_field("name1").should("have.value", "Komal");
		cy.get_field("email").should("have.value", "komal@test.com");
		cy.get_field("phone").should("have.value", "9432380001");
	});

	it("Deleting the doc", () => {
		//Deleting the inserted document
		cy.go_to_list("Test Data Control");
		cy.get(".list-row-checkbox").eq(0).click({ force: true });
		cy.get(".actions-btn-group > .btn").contains("Actions").click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button("Yes");
	});
});
