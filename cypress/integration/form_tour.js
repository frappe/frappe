context('Form Tour', () => {
	before(() => {
		cy.login();
		cy.visit('/app/form-tour');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_form_tour");
		});
	});

	const open_test_form_tour = () => {
		cy.visit('/app/form-tour/Test Form Tour');
		cy.get('button[data-label="Show%20Tour"]').should('be.visible').and('contain', 'Show Tour').as('show_tour');
		cy.get('@show_tour').click();
		cy.wait(500);
		cy.url().should('include', '/app/contact');
	};

	it('jump to a form tour', open_test_form_tour);

	it('navigates a form tour', () => {
		open_test_form_tour();

		cy.get('#driver-popover-item').should('be.visible');
		cy.get('.frappe-control[data-fieldname="first_name"]').as('first_name');
		cy.get('@first_name').should('have.class', 'driver-highlighted-element');
		cy.get('.driver-next-btn').as('next_btn');

		// next btn shouldn't move to next step, if first name is not entered
		cy.get('@next_btn').click();
		cy.wait(500);
		cy.get('@first_name').should('have.class', 'driver-highlighted-element');

		// after filling the field, next step should be highlighted
		cy.fill_field('first_name', 'Test Name', 'Data');
		cy.wait(500);
		cy.get('@next_btn').click();
		cy.wait(500);

		// assert field is highlighted
		cy.get('.frappe-control[data-fieldname="last_name"]').as('last_name');
		cy.get('@last_name').should('have.class', 'driver-highlighted-element');
		
		// after filling the field, next step should be highlighted
		cy.fill_field('last_name', 'Test Last Name', 'Data');
		cy.wait(500);
		cy.get('@next_btn').click();
		cy.wait(500);

		// assert field is highlighted
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as('phone_nos');
		cy.get('@phone_nos').should('have.class', 'driver-highlighted-element');
		
		// move to next step
		cy.wait(500);
		cy.get('@next_btn').click();
		cy.wait(500);
		
		// assert add row btn is highlighted
		cy.get('@phone_nos').find('.grid-add-row').as('add_row');
		cy.get('@add_row').should('have.class', 'driver-highlighted-element');

		// add a row & move to next step
		cy.wait(500);
		cy.get('@add_row').click();
		cy.wait(500);

		// assert table field is highlighted
		cy.get('.grid-row-open .frappe-control[data-fieldname="phone"]').as('phone');
		cy.get('@phone').should('have.class', 'driver-highlighted-element');
		// enter value in a table field
		cy.fill_table_field('phone_nos', '1', 'phone', '1234567890');

		// move to collapse row step
		cy.wait(500);
		cy.get('@next_btn').click();
		cy.wait(500);

		// collapse row
		cy.get('.grid-row-open .grid-collapse-row').click();
		cy.wait(500);
		
		// assert save btn is highlighted
		cy.get('.primary-action').should('have.class', 'driver-highlighted-element');
		cy.get('@next_btn').should('contain', 'Save');

	});
});
	