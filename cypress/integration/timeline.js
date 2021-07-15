context('Timeline', () => {
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

	it('Adding Comment', () => {
        cy.visit('/app/todo');
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.comment-input-container > .frappe-control > .ql-container > .ql-editor').should('contain','');
        cy.get('.comment-input-container > .frappe-control > .ql-container > .ql-editor').type('Testing Timeline');
        cy.get('.comment-input-wrapper > .btn').contains('Comment').click();

	});

        it('Editing, saving and deleting the comment', () => {
        cy.get('.timeline-content').should('contain','Testing Timeline');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > .btn').eq(0).first().click();
        cy.get('.timeline-content > .timeline-message-box > .comment-edit-box > .frappe-control > .ql-container > .ql-editor').first().type(' 123');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > .btn').eq(0).first().click();
        cy.get('.timeline-content').should('contain','Testing Timeline 123');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > .btn').eq(0).first().click();
        cy.get('.actions > .btn').eq(1).first().click();
        cy.get('.timeline-content').should('contain','Testing Timeline 123');
        cy.get('.actions > .btn > .icon').first().click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Yes').click();
        cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
        cy.get(':nth-child(11) > .grey-link').click();
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').contains('Yes').click();
	});
});