context('Dashboard Chart', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	it('Check filter populate for child table doctype', () => {
		cy.intercept('POST', '/api/method/frappe.client.validate_link').as('validate_link');
		cy.intercept('POST', '/api/method/frappe.desk.search.search_link').as('search_link');

		cy.visit('/app/dashboard-chart/new-dashboard-chart-1');
		cy.get('[data-fieldname="parent_document_type"]').should('have.css', 'display', 'none');
		cy.fill_field('chart_name', 'Test Chart', 'Data');

		cy.get('.frappe-control[data-fieldname=document_type] input').focus().as('input');
		cy.wait('@search_link');
		cy.get('@input').type('Workspace Link', { delay: 100 }).blur();
		cy.wait('@validate_link');
		cy.get('@input').should('have.value', 'Workspace Link');


		cy.get('[data-fieldname="filters_json"]').click().wait(200);
		cy.get('.modal-body .filter-action-buttons .add-filter').click();
		cy.get('.modal-body .fieldname-select-area').click();
		cy.get('.modal-actions .btn-modal-close').click();
	});
});