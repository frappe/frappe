context('List View Settings', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/app/website');
	});
	it('Default settings', () => {
		cy.visit('/app/List/DocType/List');
		cy.clear_filters();
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.list-stats').should('contain', "Tags");
	});
	it('disable count and sidebar stats then verify', () => {
		cy.wait(300);
		cy.visit('/app/List/DocType/List');
		cy.clear_filters();
		cy.wait(300);
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.menu-btn-group button').click();
		cy.get('.dropdown-menu li').filter(':visible').contains('List Settings').click();
		cy.get('.modal-dialog').should('contain', 'DocType Settings');

		cy.findByLabelText('Disable Count').check({ force: true });
		cy.findByLabelText('Disable Sidebar Stats').check({ force: true });
		cy.findByRole('button', {name: 'Save'}).click();

		cy.reload({ force: true });

		cy.get('.list-count').should('be.empty');
		cy.get('.list-sidebar .list-tags').should('not.exist');

		cy.get('.menu-btn-group button').click({ force: true });
		cy.get('.dropdown-menu li').filter(':visible').contains('List Settings').click();
		cy.get('.modal-dialog').should('contain', 'DocType Settings');
		cy.findByLabelText('Disable Count').uncheck({ force: true });
		cy.findByLabelText('Disable Sidebar Stats').uncheck({ force: true });
		cy.findByRole('button', {name: 'Save'}).click();
	});
});
