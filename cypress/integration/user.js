context('User', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});

	it('user navigation settings', () => {
		// go to Administrator's user settings page ond open desktop section
		cy.visit('/desk#Form/User/Administrator');
		cy.get('a.h6.uppercase').contains('Desktop').click({multiple: true});

		// change to sidebar navigation
		cy.get('select[data-fieldname="desk_navigation"]').select('Sidebar');
		cy.get('.control-value').should('contain', 'Sidebar');

		// set homepage to 'permission-manager' and save user settings
		cy.get('input[data-fieldname="homepage"]').clear().type('permission-manager{enter}', { delay: 100 });
		cy.get('button.btn-primary').contains('Save').click();
		cy.wait(2000);

		// ensure that desk sidebar is visible
		cy.get('#desk_sidebar_div').should('be.visible');

		// ensure layout is full width when sidebar is active
		cy.get('.app-container').each(($div, i, $divs) => {
			expect($div).to.have.class('container-fluid');
		});

		// click homepage link and ensure that it navigates to Permission Manager
		cy.get('.navbar-home').click();
		cy.get('#page-permission-manager').should('be.visible');

		// refresh page
		cy.reload();

		// go to Administrator's user settings page ond open desktop section
		cy.visit('/desk#Form/User/Administrator');
		cy.get('a.h6.uppercase').contains('Desktop').click({multiple: true});

		// change to desktop navigation and save user settings
		cy.get('select[data-fieldname="desk_navigation"]').select('Desktop');
		cy.get('button.btn-primary').contains('Save').click();
		cy.wait(2000);

		// click homepage link and ensure that it navigates to Desktop
		cy.get('.navbar-home').click();
		cy.get('#page-desktop').should('be.visible');

	});

});
