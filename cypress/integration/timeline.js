context('Timeline', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

	it('Adding new ToDo, adding new comment, verifying comment addition & deletion and deleting ToDo', () => {
		//Adding new ToDo
		cy.click_listview_primary_button('Add ToDo');
		cy.get('.modal-footer > .custom-actions > .btn').contains('Edit in full page').click();
		cy.get('.row > .section-body > .form-column > form > .frappe-control > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').eq(0).type('Test ToDo', {force: true});
		cy.wait(200);
		cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .primary-action').contains('Save').click();
		cy.wait(700);
		cy.visit('/app/todo');
		cy.get('.list-row > .level-left > .list-subject > .level-item.ellipsis > .ellipsis').eq(0).click();

		//To check if the comment box is initially empty and tying some text into it
		cy.get('.comment-input-container > .frappe-control > .ql-container > .ql-editor').should('contain', '').type('Testing Timeline');

		//Adding new comment
		cy.get('.comment-input-wrapper > .btn').contains('Comment').click();

		//To check if the commented text is visible in the timeline content
		cy.get('.timeline-content').should('contain', 'Testing Timeline');

		//Editing comment
		cy.click_timeline_action_btn(0);
		cy.get('.timeline-content > .timeline-message-box > .comment-edit-box > .frappe-control > .ql-container > .ql-editor').first().type(' 123');
		cy.click_timeline_action_btn(0);

		//To check if the edited comment text is visible in timeline content
		cy.get('.timeline-content').should('contain', 'Testing Timeline 123');

		//Discarding comment
		cy.click_timeline_action_btn(0);
		cy.get('.actions > .btn').eq(1).first().click();

		//To check if after discarding the timeline content is same as previous
		cy.get('.timeline-content').should('contain', 'Testing Timeline 123');

		//Deleting the added comment
		cy.get('.actions > .btn > .icon').first().click();
		cy.get('.modal-footer > .standard-actions > .btn-primary').contains('Yes').click();
		cy.click_modal_primary_button('Yes');

		//Deleting the added ToDo
		cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click({force: true});
		cy.get('.menu-btn-group > .dropdown-menu > li > .grey-link').eq(17).click({force: true});
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').contains('Yes').click({force: true});
	});
});