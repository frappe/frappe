context('Web Form', () => {
	before(() => {
		cy.login('Administrator', 'frappe')
	});

	it('Navigate and Submit a WebForm', () => {
		cy.visit('/update-profile');
		cy.get_field('last_name', 'Data').type('_Test User', {force: true}).wait(200);
		cy.get('.web-form-actions .btn-primary').click();
		cy.wait(500);
		cy.get('.modal.show > .modal-dialog').should('be.visible');
	});

	it('Timeline should have submit and cancel activity information', () => {
		cy.call('frappe.tests.ui_test_helpers.update_webform_to_multistep').then(r => {
			cy.visit('/update-profile');
			cy.get_field('last_name', 'Data').type('_Test User', {force: true}).wait(200);
			cy.get('.btn-next').should('be.visible');
			cy.get('.web-form-footer .btn-primary').should('not.be.visible');
			cy.get('.btn-next').click();
			cy.get('.btn-previous').should('be.visible');
			cy.get('.btn-next').should('not.be.visible');
			cy.get('.web-form-footer .btn-primary').should('be.visible');
			cy.get('.web-form-actions .btn-primary').click();
			cy.wait(500);
			cy.get('.modal.show > .modal-dialog').should('be.visible');
		});
	});
});
