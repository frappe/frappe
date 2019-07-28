context('Table MultiSelect', () => {
	beforeEach(() => {
		cy.login();
	});

	let name = 'table multiselect' + Math.random().toString().slice(2, 8);

	it('select value from multiselect dropdown', () => {
		cy.new_form('Assignment Rule');
		cy.fill_field('__newname', name);
		cy.fill_field('document_type', 'ToDo');
		cy.fill_field('assign_condition', 'status=="Open"', 'Code');
		cy.get('input[data-fieldname="users"]').focus().as('input');
		cy.get('input[data-fieldname="users"] + ul').should('be.visible');
		cy.get('@input').type('test{enter}', { delay: 100 });
		cy.get('.frappe-control[data-fieldname="users"] .form-control .tb-selected-value')
			.first().as('selected-value');
		cy.get('@selected-value').should('contain', 'test@erpnext.com');

		cy.server();
		cy.route('POST', '/api/method/frappe.desk.form.save.savedocs').as('save_form');
		// trigger save
		cy.get('.primary-action').click();
		cy.wait('@save_form').its('status').should('eq', 200);
		cy.get('@selected-value').should('contain', 'test@erpnext.com');
	});

	it('delete value using backspace', () => {
		cy.go_to_list('Assignment Rule');
		cy.get(`.list-subject:contains("table multiselect")`).last().find('a').click();
		cy.get('input[data-fieldname="users"]').focus().type('{backspace}');
		cy.get('.frappe-control[data-fieldname="users"] .form-control .tb-selected-value')
			.should('not.exist');
	});

	it('delete value using x', () => {
		cy.go_to_list('Assignment Rule');
		cy.get(`.list-subject:contains("table multiselect")`).last().find('a').click();
		cy.get('.frappe-control[data-fieldname="users"] .form-control .tb-selected-value').as('existing_value');
		cy.get('@existing_value').find('.btn-remove').click();
		cy.get('@existing_value').should('not.exist');
	});

	it('navigate to selected value', () => {
		cy.go_to_list('Assignment Rule');
		cy.get(`.list-subject:contains("table multiselect")`).last().find('a').click();
		cy.get('.frappe-control[data-fieldname="users"] .form-control .tb-selected-value').as('existing_value');
		cy.get('@existing_value').find('.btn-link-to-form').click();
		cy.location('hash').should('contain', 'Form/User/test@erpnext.com');
	});
});
