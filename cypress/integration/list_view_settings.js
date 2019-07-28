context('List View Settings', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/desk');
	});
	it('Default settings', () => {
		cy.visit('/desk#List/DocType/List');
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.sidebar-stat').should('contain', "Tags");
	});
	it('disable count and sidebar stats then verify', () => {
		cy.visit('/desk#List/DocType/List');
		cy.get('.list-count').should('contain', "20 of");
		cy.get('button').contains('Menu').click();
		cy.get('.dropdown-menu li').filter(':visible').contains('Settings').click();
		cy.get('.modal-dialog').should('contain', 'Settings');

		cy.get('input[data-fieldname="disable_count"]').check({force: true});
		cy.get('input[data-fieldname="disable_sidebar_stats"]').check({force: true});
		cy.get('button').filter(':visible').contains('Save').click();

		cy.reload();

		cy.get('.list-count').should('be.empty');
		cy.get('.list-sidebar .sidebar-stat').should('not.exist');

		cy.get('button').contains('Menu').click({force: true});
		cy.get('.dropdown-menu li').filter(':visible').contains('Settings').click();
		cy.get('.modal-dialog').should('contain', 'Settings');
		cy.get('input[data-fieldname="disable_count"]').uncheck({force: true});
		cy.get('input[data-fieldname="disable_sidebar_stats"]').uncheck({force: true});
		cy.get('button').filter(':visible').contains('Save').click();
	});
});
