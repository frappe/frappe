context('Timeline Email', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

	it('Adding new ToDo', () => {
		cy.click_listview_primary_button('Add ToDo');
		cy.get('.custom-actions:visible > .btn').contains("Edit Full Form").click({delay: 500});
		cy.fill_field("description", "Test ToDo",  "Text Editor");
		cy.wait(500);
		cy.get('.primary-action').contains('Save').click({force: true});
		cy.wait(700);
	});

	it('Adding email and verifying timeline content for email attachment', () => {
		cy.visit('/app/todo');
		cy.click_listview_row_item_with_text('Test ToDo');

		//Creating a new email
		cy.get('.timeline-actions > .timeline-item > .action-buttons > .action-btn').click();
		cy.fill_field('recipients', 'test@example.com', 'MultiSelect');
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-body > :nth-child(1) > .form-layout > .form-page > :nth-child(3) > .section-body > .form-column > form > [data-fieldtype="Text Editor"] > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').type('Test Mail');

		//Adding attachment to the email
		cy.get('.add-more-attachments > .btn').click();
		cy.get('.mt-2 > .btn > .mt-1').eq(2).click();
		cy.get('.input-group > .form-control').type('https://wallpaperplay.com/walls/full/8/2/b/72402.jpg');
		cy.get('.btn-primary').contains('Upload').click();

		//Sending the email
		cy.click_modal_primary_button('Send', {delay: 500});

		//To check if the sent mail content is shown in the timeline content
		cy.get('[data-doctype="Communication"] > .timeline-content').should('contain', 'Test Mail');

		//To check if the attachment of email is shown in the timeline content
		cy.get('.timeline-content').should('contain', 'Added 72402.jpg');

		//Deleting the sent email
		cy.get('[title="Open Communication"] > .icon').first().click({force: true});
		cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
		cy.get('#page-Communication > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .dropdown-menu > li > .grey-link').eq(9).click();
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').click();
	});

	it('Deleting attachment and ToDo', () => {
		cy.visit('/app/todo');
		cy.click_listview_row_item_with_text('Test ToDo');

		//Removing the added attachment
		cy.get('.attachment-row > .data-pill > .remove-btn > .icon').click();
		cy.wait(500);
		cy.get('.modal-footer:visible > .standard-actions > .btn-primary').contains('Yes').click();

		//To check if the removed attachment is shown in the timeline content
		cy.get('.timeline-content').should('contain', 'Removed 72402.jpg');
		cy.wait(500);

		//To check if the discard button functionality in email is working correctly
		cy.get('.timeline-actions > .timeline-item > .action-buttons > .action-btn').click();
		cy.fill_field('recipients', 'test@example.com', 'MultiSelect');
		cy.get('.modal-footer > .standard-actions > .btn-secondary').contains('Discard').click();
		cy.wait(500);
		cy.get('.timeline-actions > .timeline-item > .action-buttons > .action-btn').click();
		cy.wait(500);
		cy.get_field('recipients', 'MultiSelect').should('have.text', '');
		cy.get('.modal-header:visible > .modal-actions > .btn-modal-close > .icon').click();

		//Deleting the added ToDo
		cy.get('.menu-btn-group:visible > .btn').click();
		cy.get('.menu-btn-group:visible > .dropdown-menu > li > .dropdown-item').contains('Delete').click();
		cy.get('.modal-footer:visible > .standard-actions > .btn-primary').click();
	});
});
