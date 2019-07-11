context('Form', () => {
	before(() => {
		cy.login();
		cy.visit('/desk');
	});

	it('create a new form', () => {
		cy.visit('/desk#Form/ToDo/New ToDo 1');
		cy.fill_field('description', 'this is a test todo', 'Text Editor').blur();
		cy.get('.page-title').should('contain', 'Not Saved');
		cy.get('.primary-action').click();
		cy.visit('/desk#List/ToDo');
		cy.location('hash').should('eq', '#List/ToDo/List');
		cy.get('.list-row').should('contain', 'this is a test todo');
	});

	it.only('server side change handlers', () => {
		cy.visit('/desk#Form/Event/New Event 1');
		cy.fill_field('subject', 'test with handler', 'Data').blur();
		cy.fill_field('starts_on', '2019-01-01 12:00:00', 'Datetime').blur();
		cy.get_input('repeat_this_event').check({force: true});
		cy.fill_field('repeat_on', 'Every Day', 'Select').blur();
		cy.get_input('monday').should('be.checked');
		cy.get_input('tuesday').should('be.checked');
		cy.get_input('saturday').should('be.checked');
		cy.get_input('sunday').should('be.checked');
	})
});
