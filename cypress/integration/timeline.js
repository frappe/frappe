context('Timeline', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

	it('Adding Comment', () => {
        cy.get('.level-item.ellipsis > .ellipsis').click();
        cy.get('.comment-input-container > .frappe-control > .ql-container > .ql-editor').should('contain','');
        cy.get('.comment-input-container > .frappe-control > .ql-container > .ql-editor').type('Testing Timeline');
        cy.get('.comment-input-wrapper > .btn').contains('Comment').click();

	});

    it('Editing, saving and deleting the comment', () => {
        cy.get('.timeline-content').should('contain','Testing Timeline');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > :nth-child(1)').first().click();
        cy.get('.timeline-content > .timeline-message-box > .comment-edit-box > .frappe-control > .ql-container > .ql-editor').first().type(' 123');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > :nth-child(1)').first().click();
        cy.get('.timeline-content').should('contain','Testing Timeline 123');
        cy.get('.timeline-content > .timeline-message-box > .justify-between > .actions > :nth-child(1)').first().click();
        cy.get('.actions > [style="display: block;"]').first().click();
        cy.get('.timeline-content').should('contain','Testing Timeline 123');
        cy.get('.actions > :nth-child(3) > .icon').first().click();
        cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Yes').click();

	});

    it('Email Feature Test', () => {
        cy.get('.timeline-actions > .btn').click();
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-body > :nth-child(1) > .form-layout > .form-page > .to_section > .section-body > .form-column > form > [title="recipients"] > .form-group > .control-input-wrapper > .control-input > .awesomplete > .input-with-feedback').type('test@example.com');
        cy.get('.modal.show > .modal-dialog > .modal-content > .modal-body > :nth-child(1) > .form-layout > .form-page > :nth-child(3) > .section-body > .form-column > form > [data-fieldtype="Text Editor"] > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').type('Test Mail');
    });
});
