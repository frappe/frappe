context('Email Feature Test', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

    it('Saving and Deleting Email Template', () => {
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.timeline-actions > .btn').click();
        cy.fill_field('recipients','test@example.com','MultiSelect');
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-body > :nth-child(1) > .form-layout > .form-page > :nth-child(3) > .section-body > .form-column > form > [data-fieldtype="Text Editor"] > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').type('Test Mail');
        cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Send').click({delay:500});
        cy.get('[data-doctype="Communication"] > .timeline-content').should('contain','Test Mail');
        cy.get('[title="Open Communication"] > .icon').click();
        cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
        cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .dropdown-menu > :nth-child(11) > .grey-link').click();
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').click();
    });

    it('Discarding Email Template', () => {
        cy.visit('/app/todo');
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.timeline-actions > .btn').click();
        cy.fill_field('recipients','test@example.com','MultiSelect'); 
        cy.get('.modal-footer > .standard-actions > .btn-secondary').contains('Discard').click();
        cy.get('.timeline-actions > .btn').click();
        cy.get_field('recipients','MultiSelect').should('have.value','');
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-header > .modal-actions > .btn-modal-close > .icon').click();  
    });

    
});
