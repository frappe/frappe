context('Grid Pagination', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/desk');
	});
	before(() => {
		cy.login();
		cy.visit('/desk');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
		});
	});
	it('creates pages for child table', () => {
		cy.visit('/desk#Form/Contact/Test Contact');
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
		cy.get('@table').find('.current-page-number').should('contain', '1');
		cy.get('@table').find('.total-page-number').should('contain', '50');
		cy.get('@table').find('.grid-body .grid-row').should('have.length', 20);
	});
	it('goes to the next and previous page', () => {
		cy.visit('/desk#Form/Contact/Test Contact');
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
		cy.get('@table').find('.next-page').click();
		cy.get('@table').find('.current-page-number').should('contain', '2');
		cy.get('@table').find('.grid-body .grid-row').first().should('have.attr', 'data-idx', '21');
		cy.get('@table').find('.prev-page').click();
		cy.get('@table').find('.current-page-number').should('contain', '1');
		cy.get('@table').find('.grid-body .grid-row').first().should('have.attr', 'data-idx', '1');
	});
	it('adds and deletes rows and changes page', ()=> {
		cy.visit('/desk#Form/Contact/Test Contact');
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('@table').find('.grid-body .row-index').should('contain', 1001);
		cy.get('@table').find('.current-page-number').should('contain', '51');
		cy.get('@table').find('.total-page-number').should('contain', '51');
		cy.get('@table').find('.grid-body .grid-row .grid-row-check').click({force: true});
		cy.get('@table').find('button.grid-remove-rows').click();
		cy.get('@table').find('.grid-body .row-index').last().should('contain', 1000);
		cy.get('@table').find('.current-page-number').should('contain', '50');
		cy.get('@table').find('.total-page-number').should('contain', '50');
	});
	it('deletes all rows', ()=> {
		cy.visit('/desk#Form/Contact/Test Contact');
		cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
		cy.get('@table').find('.grid-heading-row .grid-row-check').click({force: true});
		cy.get('@table').find('button.grid-remove-all-rows').click();
		cy.get('@table').find('.grid-body .grid-row').should('have.length', 0);
	});
});