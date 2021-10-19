context('Dashboard Chart', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
	});

	it('Check filter populate for child table doctype', () => {
		cy.visit('/app/dashboard-chart/new-dashboard-chart-1');
		cy.get('[data-fieldname="parent_document_type"]').should('have.css', 'display', 'none');

		cy.fill_field('document_type', 'Workspace Link', 'Link').focus().blur();
		cy.get_field('document_type', 'Link').should('have.value', 'Workspace Link');
		cy.wait(500);

		cy.fill_field('chart_name', 'Test Chart', 'Data');

		cy.get('[data-fieldname="filters_json"]').click().wait(200);
		cy.get('.modal-body .filter-action-buttons .add-filter').click();
		cy.get('.modal-body .fieldname-select-area').click();
		cy.get('.modal-actions .btn-modal-close').click();
	});
});