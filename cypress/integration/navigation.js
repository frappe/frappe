context('Navigation', () => {
	before(() => {
		cy.login();
	});
	it('Navigate to route with hash in document name', () => {
		cy.insert_doc('ToDo', {'__newname': 'ABC#123', 'description': 'Test this', 'ignore_duplicate': true});
		cy.visit('/app/todo/ABC#123');
		cy.title().should('eq', 'Test this - ABC#123');
		cy.get_field('description', 'Text Editor').contains('Test this');
		cy.go('back');
		cy.title().should('eq', 'Website');
	});

	it.only('Navigate to previous page after login', () => {
		cy.visit('/app/todo');
		cy.get('.page-head').findByTitle('To Do').should('be.visible');
		cy.request('/api/method/logout');
		cy.reload().as('reload');
		cy.get('@reload').get('.page-card .btn-primary').contains('Login').click();
		cy.location('pathname').should('eq', '/login');
		cy.login();
		cy.visit('/app');
		cy.location('pathname').should('eq', '/app/todo');
	});
});
