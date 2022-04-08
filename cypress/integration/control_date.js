context('Date Control', () => {
	before(() => {
		cy.login();
		cy.visit('/app/doctype');
		return cy.window().its('frappe').then(frappe => {
			return frappe.xcall('frappe.tests.ui_test_helpers.create_doctype', {
				name: 'Test Date Control',
				fields: [
					{
						"label": "Date",
						"fieldname": "date",
						"fieldtype": "Date",
						"in_list_view": 1
					},
				]
			});
		});
	});
	it('Selecting a date from the datepicker', () => {
		cy.new_form('Test Date Control');
		cy.get_field('date', 'Date').click();
		cy.get('.datepicker--nav-title').click();
		cy.get('.datepicker--nav-title').click({force: true});


		//Inputing values in the date field
		cy.get('.datepicker--years > .datepicker--cells > .datepicker--cell[data-year=2020]').click();
		cy.get('.datepicker--months > .datepicker--cells > .datepicker--cell[data-month=0]').click();
		cy.get('.datepicker--days > .datepicker--cells > .datepicker--cell[data-date=15]').click();

		//Verifying if the selected date is displayed in the date field
		cy.get_field('date', 'Date').should('have.value', '01-15-2020');		
	});

	it('Checking next and previous button', () => {
		cy.get_field('date', 'Date').click();	

		//Clicking on the next button in the datepicker
		cy.get('.datepicker--nav-action[data-action=next]').click();

		//Selecting a date from the datepicker
		cy.get('.datepicker--cell[data-date=15]').click({force: true});

		//Verifying if the selected date has been displayed in the date field
		cy.get_field('date', 'Date').should('have.value', '02-15-2020');	
		cy.wait(500);
		cy.get_field('date', 'Date').click();

		//Clicking on the previous button in the datepicker
		cy.get('.datepicker--nav-action[data-action=prev]').click();

		//Selecting a date from the datepicker
		cy.get('.datepicker--cell[data-date=15]').click({force: true});

		//Verifying if the selected date has been displayed in the date field
		cy.get_field('date', 'Date').should('have.value', '01-15-2020');
	});

	it('Clicking on "Today" button gives todays date', () => {
		cy.get_field('date', 'Date').click();	

		//Clicking on "Today" button
		cy.get('.datepicker--button').click();

		//Picking up the todays date
		const todays_date = Cypress.moment().format('MM-DD-YYYY');

		//Verifying if clicking on "Today" button matches today's date
		cy.get_field('date', 'Date').should('have.value', todays_date);
	});
});