context('Sidebar', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/doctype');
	});

	it('Assigned To counter', () => {
        cy.get('.list-group-by-fields > :nth-child(1) > .btn').click();
        cy.get('.empty-state').should('contain','No filters found');
        cy.get('.list-group-by-fields > :nth-child(2) > .btn').click({force:true});
        cy.get('.group-by-item > .dropdown-item').should('contain','Me');
        cy.get(':nth-child(3) > .list-row').click();
        cy.get('.form-assignments > .flex > .text-muted').click();
        cy.get_field('assign_to_me','Check').click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').click();
        cy.get('#navbar-breadcrumbs > :nth-child(1)').click();
        cy.get('.list-group-by-fields > :nth-child(1) > .btn').click();
        //cy.get('dropdown-menu group-by-dropdown show').should('have.value','1');
        cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item').should('contain','1');
        //cy.get_field('assign_to','MultiSelectPills').type('kom{enter}',{delay:500, force:true}).blur();
	});

        it('Check if filter is applied', () => {
        cy.get('.filter-selector > .btn').should('contain','1 filter');
        cy.get('.group-by-field.show > .dropdown-menu > .group-by-item > .dropdown-item > .group-by-value').click();
        cy.get('.filter-selector > .btn').should('contain','2 filters').click();
        cy.get(':nth-child(3) > .list_filter > .fieldname-select-area > .awesomplete > .form-control').should('have.value','Assigned To');
        cy.get(':nth-child(3) > .list_filter > .col-sm-3 > .condition').should('have.value','like');
        cy.get(':nth-child(3) > .list_filter > :nth-child(3) > .filter-field > .form-group > .input-with-feedback').should('have.value','%Administrator%');
        cy.get(':nth-child(3) > .list_filter > .col-sm-1 > .remove-filter > .icon').click();
        cy.get('.filter-selector > .btn').click();
        cy.get('.filter-selector > .btn').should('contain','1 filter');
        });

        it('Removing the Assignment', () => {
        cy.get(':nth-child(3) > .list-row').click();
        cy.get('.assignments > .avatar-group > .avatar > .avatar-frame').click();
        cy.get('.remove-btn').click({force: true});
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-header > .modal-actions > .btn-modal-close').click();
        cy.get('#navbar-breadcrumbs > :nth-child(1)').click();
        cy.get('.list-group-by-fields > :nth-child(1) > .btn').click();
        cy.get('.empty-state').should('contain','No filters found');
        });
});
