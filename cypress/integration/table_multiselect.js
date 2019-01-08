context('Table MultiSelect', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
	});

	it('select value from multiselect dropdown', () => {
		cy.visit('/desk#Form/ToDo/New ToDo 1');
		cy.fill_field('description', 'asdf', 'Text Editor').blur();
		cy.get('input[data-fieldname="assign_to"]').focus().as('input');
		cy.get('input[data-fieldname="assign_to"] + ul').should('be.visible');
		cy.get('@input').type('faris{enter}', { delay: 100 });
		cy.get('.frappe-control[data-fieldname="assign_to"] .form-control .tb-selected-value')
			.first().as('selected-value');
		cy.get('@selected-value').should('contain', 'faris@erpnext.com');

		cy.server();
		cy.route('POST', '/').as('save_form');
		// trigger save
		cy.get('.primary-action').click();
		cy.wait('@save_form').its('status').should('eq', 200);
		cy.get('@selected-value').should('contain', 'faris@erpnext.com');
	});

	it('delete value using backspace', () => {
		cy.visit('/desk#List/ToDo/List');
		cy.get('.list-row a').should('exist');
		cy.get('.list-subject').last().find('a').click();
		cy.get('input[data-fieldname="assign_to"]').focus().type('{backspace}');
		cy.get('.frappe-control[data-fieldname="assign_to"] .form-control .tb-selected-value')
			.should('not.exist');
	});

	it('delete value using x', () => {
		cy.visit('/desk#List/ToDo/List');
		cy.get('.list-row a').should('exist');
		cy.get('.list-subject').last().find('a').click();
		cy.get('.frappe-control[data-fieldname="assign_to"] .form-control .tb-selected-value').as('existing_value');
		cy.get('@existing_value').find('.btn-remove').click();
		cy.get('@existing_value').should('not.exist');
	});

	it('navigate to selected value', () => {
		cy.visit('/desk#List/ToDo/List');
		cy.get('.list-row a').should('exist');
		cy.get('.list-subject').last().find('a').click();
		cy.get('.frappe-control[data-fieldname="assign_to"] .form-control .tb-selected-value').as('existing_value');
		cy.get('@existing_value').find('.btn-link-to-form').click();
		cy.location('hash').should('contain', 'Form/User/faris@erpnext.com');
	});
});
