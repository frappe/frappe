context('Dashboard links', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/user');
	});

	it('Adding a new contact, checking for the counter on the dashboard and deleting the created contact', () => {
		cy.get('.list-row-col > .level-item > .ellipsis').eq(0).click();

		//To check if initially the dashboard contains only the "Contact" link and there is no counter
		cy.get('[data-doctype="Contact"]').should('contain','Contact');

		//Adding a new contact
		cy.get('.btn[data-doctype="Contact"]').click();
		cy.get('.has-error > .form-group > .control-input-wrapper > .control-input > .input-with-feedback').type('Admin');
		cy.get('#page-Contact > .page-head > .container > .row > .col > .standard-actions > .primary-action').click();
		cy.visit('/app/user');
		cy.get('.list-row-col > .level-item > .ellipsis').eq(0).click();

		//To check if the counter for contact doc is "1" after adding the contact
		cy.get('[data-doctype="Contact"] > .count').should('contain','1');
		cy.get('[data-doctype="Contact"]').contains('Contact').click(); 

		//Deleting the newly created contact
		cy.visit('/app/contact');
		cy.get('.list-subject > .select-like > .list-row-checkbox').eq(0).click();
		cy.get('.actions-btn-group > .btn').contains('Actions').click();
		cy.get('.actions-btn-group > .dropdown-menu > li > .grey-link').eq(5).click();
		cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Yes').click({delay : 700});


		//To check if the counter from the "Contact" doc link is removed
		cy.visit('/app/user');
		cy.wait(700);
		cy.get('.list-row-col > .level-item > .ellipsis').eq(0).click();
		cy.get('[data-doctype="Contact"]').should('contain','Contact');
	});
});