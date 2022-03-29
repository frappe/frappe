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
		cy.get_field('date','Date').click();
		cy.get('.datepicker--nav-title').click();
		cy.get('.datepicker--nav-title').click({force: true});


		//Inputing values in the date field
		cy.get('.datepicker--years > .datepicker--cells > .datepicker--cell[data-year=2020]').click();
		cy.get('.datepicker--months > .datepicker--cells > .datepicker--cell[data-month=0]').click();
		cy.get('.datepicker--days > .datepicker--cells > .datepicker--cell[data-date=15]').click();

		//Verifying if the selected date is displayed in the date field
		cy.get_field('date','Date').should('have.value', '01-15-2020');		
	});

	it('Checking next and previous button', () => {
		cy.get_field('date','Date').click();	

		//Clicking on the next button in the datepicker
		cy.get('.datepicker--nav-action[data-action=next]').click();

		//Selecting a date from the datepicker
		cy.get('.datepicker--cell[data-date=15]').click({force: true});

		//Verifying if the selected date has been displayed in the date field
		cy.get_field('date','Date').should('have.value', '02-15-2020');	
		cy.wait(500);
		cy.get_field('date','Date').click();

		//Clicking on the previous button in the datepicker
		cy.get('.datepicker--nav-action[data-action=prev]').click();

		//Selecting a date from the datepicker
		cy.get('.datepicker--cell[data-date=15]').click({force: true});

		//Verifying if the selected date has been displayed in the date field
		cy.get_field('date','Date').should('have.value', '01-15-2020');
	});

	it('Clicking on "Today" button gives todays date', () => {
		cy.get_field('date','Date').click();	

		//Clicking on "Today" button
		cy.get('.datepicker--button').click();

		//Picking up the todays date
		const todaysDate = Cypress.moment().format('MM-DD-YYYY');
		cy.log(todaysDate);

		//Verifying if clicking on "Today" button matches today's date
		cy.get_field('date','Date').should('have.value', todaysDate);
	});

	it.only('Configuring first day of the week', () => {
		//Visiting "System Settings" page
		cy.visit('/app/system-settings/System%20Settings');

		//Visiting the "Date and Number Format" section
		cy.contains('Date and Number Format').click();

		//Changing the configuration for "First day of the week" field
		cy.get('select[data-fieldname="first_day_of_the_week"]').select('Tuesday');
		cy.get('.page-head .page-actions').findByRole('button', {name: 'Save'}).click();
		cy.new_form('Test Date Control');
		cy.get_field('date','Date').click();

		//Checking if the first day shown in the datepicker is the one which is configured in the System Settings Page
		cy.get('.datepicker--days-names').eq(0).should('contain.text', 'Tu');
		cy.visit('/app/doctype');

		//Adding filter in the doctype list
		cy.add_filter();
		cy.get('.fieldname-select-area').type('Created On{enter}');
		cy.get('.filter-field > .form-group > .input-with-feedback').click();

		//Checking if the first day shown in the datepicker is the one which is configured in the System Settings Page
		cy.get('.datepicker--days-names').eq(0).should('contain.text', 'Tu');

		//Adding event
		cy.visit('/app/event');
		cy.click_listview_primary_button('Add Event');
		cy.get('textarea[data-fieldname=subject]').type('Test');
		//cy.fill_field('subject','Test','textarea');
		cy.get('form > .has-error > .form-group > .control-input-wrapper > .control-input > .input-with-feedback[data-fieldtype="Datetime"]').click();
		cy.get('.datepicker.active > .datepicker--content > .datepicker--days > .datepicker--cells > .datepicker--cell[data-date=10]').click({force: true});
		cy.click_listview_primary_button('Save');
		cy.visit('/app/event');
		cy.get('.custom-btn-group > .btn').click();

		//Opening Calendar view for the event created
		cy.get('[data-view="Calendar"] > .grey-link').click();

		//Checking if the calendar view has the first day as the configured day in the System Settings Page
		cy.get('.fc-head-container').eq(0).should('contain.text', 'Tue');

		//Deleting the created event
		cy.visit('/app/event');
		cy.get('.list-row-checkbox').eq(0).click();
		cy.get('.actions-btn-group > .btn').contains('Actions').click();
		cy.get('.actions-btn-group > .dropdown-menu [data-label="Delete"]').click();
		cy.click_modal_primary_button('Yes');
	});
});