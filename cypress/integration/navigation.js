context('Navigation', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});
	it('Navigate to route with hash in document name', () => {
		cy.insert_doc('ToDo', {'__newname': 'ABC#123', 'description': 'Test this', 'ignore_duplicate': true});
		cy.visit('/app/todo/ABC#123');
		cy.title().should('eq', 'Test this - ABC#123');
		cy.get_field('description', 'Text Editor').contains('Test this');
		cy.go('back');
		cy.title().should('eq', 'Website');
	});
});
