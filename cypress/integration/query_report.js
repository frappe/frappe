context('Query Report', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	it('add custom column in report', () => {
		cy.visit('/app/query-report/Permitted Documents For User');

		cy.get('.page-form.flex', { timeout: 60000 }).should('have.length', 1).then(() => {
			cy.get('#page-query-report input[data-fieldname="user"]').as('input');
			cy.get('@input').focus().type('test@erpnext.com', { delay: 100 }).blur();
			cy.wait(300);
			cy.get('#page-query-report input[data-fieldname="doctype"]').as('input-test');
			cy.get('@input-test').focus().type('Role', { delay: 100 }).blur();

			cy.get('.datatable').should('exist');
			cy.get('.menu-btn-group button').click({ force: true });
			cy.get('.dropdown-menu li').contains('Add Column').click({ force: true });
			cy.get('.modal-dialog').should('contain', 'Add Column');
			cy.get('select[data-fieldname="doctype"]').select("Role", { force: true });
			cy.get('select[data-fieldname="field"]').select("Role Name", { force: true });
			cy.get('select[data-fieldname="insert_after"]').select("Name", { force: true });
			cy.get('button').contains('Submit').click({ force: true });
			cy.get('.menu-btn-group button').click({ force: true });
			cy.get('.dropdown-menu li').contains('Save').click({ force: true });
			cy.get('.modal-dialog').should('contain', 'Save Report');

			cy.get('input[data-fieldname="report_name"]').type("Test Report", { delay: 100, force: true });
			cy.get('button').contains('Submit').click({ timeout: 1000, force: true });
		});
	});
});