context('Relative Timeframe', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.ui_test_helpers.create_todo_records");
		});
	});
	it('sets relative timespan filter for last week and filters list', () => {
		cy.visit('/app/List/ToDo/List');
		cy.clear_filters();
		cy.get('.list-row:contains("this is fourth todo")').should('exist');
		cy.add_filter();
		cy.get('.fieldname-select-area').should('exist');
		cy.get('.fieldname-select-area input').type("Due Date{enter}", { delay: 100 });
		cy.get('select.condition.form-control').select("Timespan");
		cy.get('.filter-field select.input-with-feedback.form-control').select("last week");
		cy.intercept('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.get('.filter-popover .apply-filters').click({ force: true });
		cy.wait('@list_refresh');
		cy.get('.list-row-container').its('length').should('eq', 1);
		cy.get('.list-row-container').should('contain', 'this is second todo');
		cy.intercept('POST', '/api/method/frappe.model.utils.user_settings.save')
			.as('save_user_settings');
		cy.clear_filters();
		cy.wait('@save_user_settings');
	});
	it('sets relative timespan filter for next week and filters list', () => {
		cy.visit('/app/List/ToDo/List');
		cy.clear_filters();
		cy.get('.list-row:contains("this is fourth todo")').should('exist');
		cy.add_filter();
		cy.get('.fieldname-select-area input').type("Due Date{enter}", { delay: 100 });
		cy.get('select.condition.form-control').select("Timespan");
		cy.get('.filter-field select.input-with-feedback.form-control').select("next week");
		cy.intercept('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.get('.filter-popover .apply-filters').click({ force: true });
		cy.wait('@list_refresh');
		cy.intercept('POST', '/api/method/frappe.model.utils.user_settings.save')
			.as('save_user_settings');
		cy.clear_filters();
		cy.wait('@save_user_settings');
	});
});
