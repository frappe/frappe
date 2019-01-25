context('Relative Timeframe', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.test_utils.create_todo_records");
		});
	});
	it('set relative filter for Previous and check list', () => {
		cy.visit('/desk#List/ToDo/List');
		cy.get('.list-row:contains("this is fourth todo")').should('exist');
		cy.get('.tag-filters-area .btn:contains("Add Filter")').click();
		cy.get('.fieldname-select-area').should('exist');
		cy.get('.fieldname-select-area input').type("Due Date{enter}", { delay: 100 });
		cy.get('select.condition.form-control').select("Previous");
		cy.get('.filter-field select.input-with-feedback.form-control').select("1 week");
		cy.server();
		cy.route({
			method: 'POST',
			url: '/'
		}).as('applyFilter');
		cy.get('.filter-box .btn:contains("Apply")').click();
		cy.wait('@applyFilter');
		cy.get('.list-row-container').its('length').should('eq', 1);
		cy.get('.list-row-container').should('contain', 'this is second todo');
		cy.get('.remove-filter.btn').click();
	});
	it('set relative filter for Next and check list', () => {
		cy.visit('/desk#List/ToDo/List');
		cy.get('.list-row:contains("this is fourth todo")').should('exist');
		cy.get('.tag-filters-area .btn:contains("Add Filter")').click();
		cy.get('.fieldname-select-area input').type("Due Date{enter}", { delay: 100 });
		cy.get('select.condition.form-control').select("Next");
		cy.get('.filter-field select.input-with-feedback.form-control').select("1 week");
		cy.server();
		cy.route({
			method: 'POST',
			url: '/'
		}).as('applyFilter');
		cy.get('.filter-box .btn:contains("Apply")').click();
		cy.wait('@applyFilter');
		cy.get('.list-row-container').its('length').should('eq', 1);
		cy.get('.list-row').should('contain', 'this is first todo');
		cy.get('.remove-filter.btn').click();
	});
});
