context('Sidebar', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/doctype');
	});

	it('Test for checking "Assigned To" counter value, adding filter and adding & removing an assignment', () => {
		cy.click_sidebar_button(0);

		//To check if no filter is available in "Assigned To" dropdown
		cy.get('.empty-state').should('contain', 'No filters found');

		cy.click_sidebar_button(1);

		//To check if "Created By" dropdown contains filter
		cy.get('.group-by-item > .dropdown-item').should('contain', 'Me');

		//Assigning a doctype to a user
		cy.click_listview_row_item(0);
		cy.get('.form-assignments > .flex > .text-muted').click();
		cy.get_field('assign_to_me', 'Check').click();
		cy.get('.modal-footer > .standard-actions > .btn-primary').click();
		cy.visit('/app/doctype');
		cy.click_sidebar_button(0);

		//To check if filter is added in "Assigned To" dropdown after assignment
		cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item').should('contain', '1');

		//To check if there is no filter added to the listview
		cy.get('.filter-selector > .btn').should('contain', 'Filter');

		//To add a filter to display data into the listview
		cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item').click();

		//To check if filter is applied
		cy.click_filter_button().should('contain', '1 filter');
		cy.get('.fieldname-select-area > .awesomplete > .form-control').should('have.value', 'Assigned To');
		cy.get('.condition').should('have.value', 'like');
		cy.get('.filter-field > .form-group > .input-with-feedback').should('have.value', '%Administrator%');

		//To remove the applied filter
		cy.get('.filter-action-buttons > div > .btn-secondary').contains('Clear Filters').click();
		cy.click_filter_button();
		cy.get('.filter-selector > .btn').should('contain', 'Filter');

		//To remove the assignment
		cy.visit('/app/doctype');
		cy.click_listview_row_item(0);
		cy.get('.assignments > .avatar-group > .avatar > .avatar-frame').click();
		cy.get('.remove-btn').click({force: true});
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-header > .modal-actions > .btn-modal-close').click();
		cy.visit('/app/doctype');
		cy.click_sidebar_button(0);
		cy.get('.empty-state').should('contain', 'No filters found');
	});
});