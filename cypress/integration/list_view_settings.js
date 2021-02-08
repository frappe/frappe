context('List View Settings', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/app/website');
	});
	it('Default settings', () => {
		cy.visit('/app/List/DocType/List');
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.list-stats').should('contain', "Tags");
	});
	it('disable count and sidebar stats then verify', () => {
		cy.wait(300);
		cy.visit('/app/List/DocType/List');
		cy.wait(300);
		cy.get('.list-count').should('contain', "20 of");
		cy.get('.menu-btn-group button').click();
		cy.get('.dropdown-menu li').filter(':visible').contains('List Settings').click();
		cy.get('.modal-dialog').should('contain', 'DocType Settings');

		cy.get('input[data-fieldname="disable_count"]').check({ force: true });
		cy.get('input[data-fieldname="disable_sidebar_stats"]').check({ force: true });
		cy.get('button').filter(':visible').contains('Save').click();

		cy.reload({ force: true });

		cy.get('.list-count').should('be.empty');
		cy.get('.list-sidebar .list-tags').should('not.exist');

		cy.get('.menu-btn-group button').click({ force: true });
		cy.get('.dropdown-menu li').filter(':visible').contains('List Settings').click();
		cy.get('.modal-dialog').should('contain', 'DocType Settings');
		cy.get('input[data-fieldname="disable_count"]').uncheck({ force: true });
		cy.get('input[data-fieldname="disable_sidebar_stats"]').uncheck({ force: true });
		cy.get('button').filter(':visible').contains('Save').click();
	});
});
