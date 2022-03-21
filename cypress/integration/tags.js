context('Tags', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/doctype');
	});
	it('Checking if initially there are no tags available', () => {
		//Clicking on the sidebar tags dropdown
		cy.get('.list-tags').click();

		//Clicking on the dropdown item "No Tags"
		cy.get('[data-label="No Tags"]').click({force: true});

		//Checking if the filter is getting applied after clicking on the item "No Tags"
		cy.get('.filter-selector > .btn').should('contain','1 filter').click();

		//Checking the values of the filter
		cy.get('.fieldname-select-area > .awesomplete > .form-control').should('have.value','Tags');
		cy.get('.condition').should('have.value','not like');
		cy.get('.filter-field > .form-group > .input-with-feedback').should('have.value','%,%');

		//Clearing the filter
		cy.get('.filter-action-buttons > div > .btn-secondary').contains('Clear Filters').click();

		//Checking if the filter is removed
		cy.get('.filter-selector > .btn').click().should('contain','Filter');
	});

	it('Adding Tag', () => {
		cy.visit('/app/doctype');

		//Clicking on the first row item of doctype listview
		cy.click_listview_row_item(0);

		//Adding a tag to the item visited
		cy.get('.tags-placeholder').type('custom_docs');
		cy.get('.form-tags > .sidebar-label').click({delay : 500});
		cy.visit('/app/doctype');

		//Clicking on the sidebar tags dropdown
		cy.get('.list-tags').click();

		//Checking if the newly created tag is visible in the dropdown
		cy.get('.stat-link .stat-label').should('contain','custom_docs');

		//Clicking on the dropdown item "custom_docs"
		cy.get('[data-label="custom_docs"] > .stat-label').click({force: true});

		//Checking if the filter for the tag is being applied on the list
		cy.get('.filter-selector > .btn').should('contain','1 filter').click();
		cy.get('.fieldname-select-area > .awesomplete > .form-control').should('have.value','Tags');
		cy.get('.condition').should('have.value','like');
		cy.get('.filter-field > .form-group > .input-with-feedback').should('have.value','custom_docs');

		//Clearing the applied filter
		cy.get('.filter-action-buttons > div > .btn-secondary').contains('Clear Filters').click();
		cy.get('.filter-selector > .btn').click();

		//Checking if the applied filter is being removed
		cy.get('.filter-selector > .btn').should('contain','Filter');
	});

	it('Searching tag using awesome bar', () => {
		//Searching the created tag using the awesome bar
		cy.get('#navbar-search').type('#custom_docs');
		cy.wait(500);
		cy.get('#navbar-search').type('{downarrow}{enter}');
		cy.get('.result-section-link').click();

		//Checking if the tag "custom_docs" is being present
		cy.get('.form-tag-row > .data-pill').should('contain','custom_docs');

		//Removing the tag
		cy.get('.btn-modal-close').click({force: true});
		cy.get('.remove-btn > .icon').click();
		cy.visit('/app/doctype');

		//Checking if the tag is being removed from the dropdown item
		cy.get('.list-tags > .list-stats > .btn').click();
		cy.get('.stat-link .stat-label').should('contain','No Tags');
	});
});