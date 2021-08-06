context('Timeline Email', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/todo');
	});

	it('Adding new ToDo, adding email and verifying timeline content for email attachment, deleting attachment and ToDo', () => {
		//Adding new ToDo
		cy.click_listview_primary_button('Add ToDo');
		cy.get('.custom-actions > .btn').trigger('click', {delay: 500});
		cy.get('.row > .section-body > .form-column > form > .frappe-control > .form-group > .control-input-wrapper > .control-input > .ql-container > .ql-editor').eq(0).type('Test ToDo', {force: true});
		cy.wait(500);
		//cy.click_listview_primary_button('Save');
		cy.get('.primary-action').contains('Save').click({force: true});
		cy.wait(700);
		cy.visit('/app/todo');
		cy.get('.list-row > .level-left > .list-subject > .level-item.ellipsis > .ellipsis').eq(0).click();

		//Creating a new email
		cy.get('.timeline-actions > .btn').click();
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
		cy.visit('/app/todo');
		cy.get('.list-row > .level-left > .list-subject > .level-item.ellipsis > .ellipsis').eq(0).click();

		//Removing the added attachment
		cy.get('.attachment-row > .data-pill > .remove-btn > .icon').click();
		cy.get('.modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').contains('Yes').click();

		//To check if the removed attachment is shown in the timeline content
		cy.get('.timeline-content').should('contain', 'Removed 72402.jpg');
		cy.wait(500);

		//To check if the discard button functionality in email is working correctly
		cy.get('.timeline-actions > .btn').click();
		cy.fill_field('recipients', 'test@example.com', 'MultiSelect'); 
		cy.get('.modal-footer > .standard-actions > .btn-secondary').contains('Discard').click();
		cy.wait(500);
		cy.get('.timeline-actions > .btn').click();
		cy.wait(500);
		cy.get_field('recipients', 'MultiSelect').should('have.text', '');
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-header > .modal-actions > .btn-modal-close > .icon').click();  

		//Deleting the added ToDo
		cy.get('#page-ToDo > .page-head > .container > .row > .col > .standard-actions > .menu-btn-group > .btn').click();
		cy.get('.menu-btn-group > .dropdown-menu > li > .grey-link').eq(17).click();
		cy.get('.modal.show > .modal-dialog > .modal-content > .modal-footer > .standard-actions > .btn-primary').click();
	});
});
