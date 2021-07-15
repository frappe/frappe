context('Sidebar', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/doctype');
	});

	it('"Assigned To" counter', () => {
        cy.get('.list-group-by-fields > .group-by-field > .btn').eq(0).click();
        cy.get('.empty-state').should('contain','No filters found');
        cy.get('.list-group-by-fields > .group-by-field > .btn').eq(1).click({force:true});
        cy.get('.group-by-item > .dropdown-item').should('contain','Me');
        cy.get('.list-row > .level-left > .list-subject > .bold > .ellipsis').eq(0).click();
        cy.get('.form-assignments > .flex > .text-muted').click();
        cy.get_field('assign_to_me','Check').click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').click();
        cy.visit('/app/doctype');
        cy.get('.list-group-by-fields > .group-by-field > .btn').eq(0).click();
        cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item').should('contain','1');
	});

    it('Check if filter is applied', () => {
        cy.get('.filter-selector > .btn').should('contain','Filter');
        cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item > .group-by-value').click();
        cy.get('.filter-selector > .btn').should('contain','1 filter').click();
        cy.get('.fieldname-select-area > .awesomplete > .form-control').should('have.value','Assigned To');
        cy.get('.condition').should('have.value','like');
        cy.get('.filter-field > .form-group > .input-with-feedback').should('have.value','%Administrator%');
        cy.get('.filter-action-buttons > div > .btn-secondary').contains('Clear Filters').click();
        cy.get('.filter-selector > .btn').click();
        cy.get('.filter-selector > .btn').should('contain','Filter');
    });

    it('Removing the Assignment', () => {
        cy.get('.list-row > .level-left > .list-subject > .bold > .ellipsis').eq(0).click();
        cy.get('.assignments > .avatar-group > .avatar > .avatar-frame').click();
        cy.get('.remove-btn').click({force: true});
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-header > .modal-actions > .btn-modal-close').click();
        cy.visit('/app/doctype');
        cy.get('.list-group-by-fields > .group-by-field > .btn').eq(0).click();
        cy.get('.empty-state').should('contain','No filters found');
    });

});