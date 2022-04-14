context('Data Control', () => {
	before(() => {
		cy.login();
		cy.visit('/app/doctype');
		return cy.window().its('frappe').then(frappe => {
			return frappe.xcall('frappe.tests.ui_test_helpers.create_doctype', {
				name: 'Test Data Control',
				fields: [
					{
						"label": "Name",
						"fieldname": "name1",
						"fieldtype": "Data",
						"options":"Name",
						"in_list_view": 1,
					},
					{
						"label": "Email-ID",
						"fieldname": "email",
						"fieldtype": "Data",
						"options":"Email",
						"in_list_view": 1,
					},
					{
						"label": "Phone No.",
						"fieldname": "phone",
						"fieldtype": "Data",
						"options":"Phone",
						"in_list_view": 1,
					},
				]
			});
		});
	});
	it('Verifying data control by inputting different patterns', () => {
		cy.new_form('Test Data Control');

		//Checking the URL for the new form of the doctype
		cy.location("pathname").should('eq', '/app/test-data-control/new-test-data-control-1');
		cy.get('.title-text').should('have.text', 'New Test Data Control');

		//Checking if the status is "Not Saved" initially
		cy.get('.indicator-pill').should('have.text', 'Not Saved');

		//Inputting data in the field
		cy.fill_field('name1', '@@###', 'Data');

		//Checking if the border color of the field changes to red
		cy.get_field('name1', 'Data').should('have.css', 'border', '1px solid rgb(236, 100, 94)');
		cy.findByRole('button', {name: 'Save'}).click();

		//Checking for the error message
		cy.get('.modal-title').should('have.text', 'Message');
		cy.get('.msgprint').should('have.text', '@@### is not a valid Name');
		cy.reload();

		cy.fill_field('name1', 'Komal{}/!', 'Data');
		cy.get_field('name1', 'Data').should('have.css', 'border', '1px solid rgb(236, 100, 94)');
		cy.findByRole('button', {name: 'Save'}).click();
		cy.get('.modal-title').should('have.text', 'Message');
		cy.get('.msgprint').should('have.text', 'Komal{}/! is not a valid Name');
		cy.reload();

		cy.fill_field('name1', 'Komal', 'Data');
		cy.get_field('name1', 'Data').should('have.css', 'border', '0px none rgb(152, 161, 169)');
		cy.fill_field('email', 'komal', 'Data');
		cy.get_field('email', 'Data').should('have.css', 'border', '1px solid rgb(236, 100, 94)');
		cy.findByRole('button', {name: 'Save'}).click();
		cy.get('.modal-title').should('have.text', 'Message');
		cy.get('.msgprint').should('have.text', 'komal is not a valid Email Address');
		cy.reload();

		cy.fill_field('email', 'komal@test', 'Data');
		cy.get_field('email', 'Data').should('have.css', 'border', '1px solid rgb(236, 100, 94)');
		cy.findByRole('button', {name: 'Save'}).click();
		cy.get('.modal-title').should('have.text', 'Message');
		cy.get('.msgprint').should('have.text', 'komal@test is not a valid Email Address');
		cy.reload();

		cy.fill_field('email', 'komal@test.com', 'Data');
		cy.get_field('email', 'Data').should('have.css', 'border', '0px none rgb(152, 161, 169)');

		cy.fill_field('phone', 'komal', 'Data');
		cy.get_field('phone', 'Data').should('have.css', 'border', '1px solid rgb(236, 100, 94)');
		cy.findByRole('button', {name: 'Save'}).click();
		cy.get('.modal-title').should('have.text', 'Message');
		cy.get('.msgprint').should('have.text', 'komal is not a valid Phone Number');
		cy.reload();

		//Inputting the data as expected and saving the document
		cy.fill_field('name1', 'Komal', 'Data');
		cy.fill_field('email', 'komal@test.com', 'Data');
		cy.fill_field('phone', '9432380001', 'Data');
		cy.get_field('phone', 'Data').should('have.css', 'border', '0px none rgb(152, 161, 169)');
		cy.findByRole('button', {name: 'Save'}).click();

		//Checking if the fields contains the data which has been filled in
		cy.location("pathname").should('not.be', '/app/test-data-control/new-test-data-control-1');
		cy.get_field('name1').should('have.value', 'Komal');
		cy.get_field('email').should('have.value', 'komal@test.com');
		cy.get_field('phone').should('have.value', '9432380001');

		//Deleting the inserted document
		cy.visit('/app/test-data-control');
		cy.get('.list-row-checkbox').eq(0).click();
		cy.get('.actions-btn-group > .btn').contains('Actions').click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button('Yes');
		cy.get('.btn-modal-close').click();
	});
});