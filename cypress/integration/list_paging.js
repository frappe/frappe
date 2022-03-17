context('List Paging', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_multiple_todo_records");
		});
	});

	it('test load more with count selection buttons', () => {
		cy.visit('/app/todo/view/report');

		cy.get('.list-paging-area .list-count').should('contain.text', '20 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '40 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '60 of');

		cy.get('.list-paging-area .btn-group .btn-paging[data-value="100"]').click();

		cy.get('.list-paging-area .list-count').should('contain.text', '100 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '200 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '300 of');

		// check if refresh works after load more
		cy.get('.page-head .standard-actions [data-original-title="Refresh"]').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '300 of');

		cy.get('.list-paging-area .btn-group .btn-paging[data-value="500"]').click();

		cy.get('.list-paging-area .list-count').should('contain.text', '500 of');
		cy.get('.list-paging-area .btn-more').click();

		cy.get('.list-paging-area .list-count').should('contain.text', '1000 of');
	});
});
