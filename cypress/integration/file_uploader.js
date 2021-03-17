context('FileUploader', () => {
	before(() => {
		cy.login();
		cy.visit('/app');
	});

	function open_upload_dialog() {
		cy.window().its('frappe').then(frappe => {
			new frappe.ui.FileUploader();
		});
	}

	it('upload dialog api works', () => {
		open_upload_dialog();
		cy.get_open_dialog().should('contain', 'Drag and drop files');
		cy.hide_dialog();
	});

	it('should accept dropped files', () => {
		open_upload_dialog();

		cy.get_open_dialog().find('.file-upload-area').attachFile('example.json', {
			subjectType: 'drag-n-drop',
		});

		cy.get_open_dialog().find('.file-name').should('contain', 'example.json');
		cy.intercept('POST', '/api/method/upload_file').as('upload_file');
		cy.get_open_dialog().find('.btn-modal-primary').click();
		cy.wait('@upload_file').its('response.statusCode').should('eq', 200);
		cy.get('.modal:visible').should('not.exist');
	});

	it('should accept uploaded files', () => {
		open_upload_dialog();

		cy.get_open_dialog().find('.btn-file-upload div:contains("Library")').click();
		cy.get('.file-filter').type('example.json');
		cy.get_open_dialog().find('.tree-label:contains("example.json")').first().click();
		cy.intercept('POST', '/api/method/upload_file').as('upload_file');
		cy.get_open_dialog().find('.btn-primary').click();
		cy.wait('@upload_file').its('response.body.message')
			.should('have.property', 'file_name', 'example.json');
		cy.get('.modal:visible').should('not.exist');
	});

	it('should accept web links', () => {
		open_upload_dialog();

		cy.get_open_dialog().find('.btn-file-upload div:contains("Link")').click();
		cy.get_open_dialog().find('.file-web-link input').type('https://github.com', { delay: 100, force: true });
		cy.intercept('POST', '/api/method/upload_file').as('upload_file');
		cy.get_open_dialog().find('.btn-primary').click();
		cy.wait('@upload_file').its('response.body.message')
			.should('have.property', 'file_url', 'https://github.com');
		cy.get('.modal:visible').should('not.exist');
	});
});
