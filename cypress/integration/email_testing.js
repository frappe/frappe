context('Email Feature Test', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

    it('Adding new ToDo', () => {
        cy.get('.primary-action').contains('Add ToDo').click();
        cy.get('.modal-footer > .custom-actions > .btn').contains('Edit in full page').click();
        cy.get('.row > .section-body > .form-column > form > .frappe-control > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').first().type('Test ToDo');
        cy.wait(200);
        cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .primary-action').contains('Save').click();
        });

    it('Saving and Deleting Email Template', () => {
        cy.visit('/app/todo');
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.timeline-actions > .btn').click();
        cy.fill_field('recipients','test@example.com','MultiSelect');
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-body > :nth-child(1) > .form-layout > .form-page > :nth-child(3) > .section-body > .form-column > form > [data-fieldtype="Text Editor"] > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').type('Test Mail');
        
        cy.get('.add-more-attachments > .btn').click();
        cy.get('.mt-2 > .btn > .mt-1').eq(2).click();
        cy.get('.input-group > .form-control').type('https://wallpaperplay.com/walls/full/8/2/b/72402.jpg');
        cy.get('.btn-primary').contains('Upload').click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Send').click({delay:500});
        cy.get('[data-doctype="Communication"] > .timeline-content').should('contain','Test Mail');
        cy.get('.timeline-content').should('contain','Added 72402.jpg');
        cy.get('[title="Open Communication"] > .icon').click();
        cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
        cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .dropdown-menu > :nth-child(11) > .grey-link').click();
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').click();
        cy.visit('/app/todo');
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.attachment-row > .data-pill > .remove-btn > .icon').click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Yes').click();
        cy.get('.timeline-content').should('contain','Removed 72402.jpg');
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
        cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
        cy.get(':nth-child(11) > .grey-link').click();
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').contains('Yes').click();
    });

    
});
