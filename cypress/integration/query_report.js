context('Form', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});

	it('add custom column in report', () => {
		cy.visit('/desk#query-report/Permitted Documents For User');

		cy.get('#page-query-report input[data-fieldname="user"]').as('input');
		cy.get('@input').focus().type('test@erpnext.com', { delay: 100 });
		cy.get('#page-query-report input[data-fieldname="doctype"]').as('input-test');
		cy.get('@input-test').focus().type('Role', { delay: 100 }).blur();
		cy.get('.datatable').should('exist');
		cy.get('.menu-btn-group .btn').click({force: true});
		cy.get('.grey-link:contains("Add Column")').click({force: true});
		cy.get('.modal-dialog select[data-fieldname="doctype"]').select("Role");
		cy.get('.modal-dialog select[data-fieldname="field"]').select("Role Name");
		cy.get('.modal-dialog select[data-fieldname="insert_after"]').select("Name");
		cy.get('.modal-dialog .btn-primary:contains("Submit")').click({force: true});
		cy.get('.menu-btn-group .btn').click({force: true});
		cy.get('.grey-link:contains("Save")').click({force: true});
		cy.get('.modal-dialog input[data-fieldname="report_name"]').type("Test Report");
		cy.get('.modal:visible .btn-primary:contains("Submit")').click({force: true});
	});
});