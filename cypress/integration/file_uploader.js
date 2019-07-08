context('FileUploader', () => {
	before(() => {
		cy.login();
		cy.visit('/desk');
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

		cy.fixture('example.json').then(fileContent => {
			cy.get_open_dialog().find('.file-upload-area').upload(
				{ fileContent, fileName: 'example.json', mimeType: 'application/json' },
				{ subjectType: 'drag-n-drop' },
			);
			cy.get_open_dialog().find('.file-info').should('contain', 'example.json');
			cy.server();
			cy.route('POST', '/api/method/upload_file').as('upload_file');
			cy.get_open_dialog().find('.btn-primary').click();
			cy.wait('@upload_file').its('status').should('be', 200);
			cy.get('.modal:visible').should('not.exist');
		});
	});

	it('should accept uploaded files', () => {
		open_upload_dialog();

		cy.get_open_dialog().find('a:contains("uploaded file")').click();
		cy.get_open_dialog().find('.tree-label:contains("example.json")').first().click();
		cy.server();
		cy.route('POST', '/api/method/upload_file').as('upload_file');
		cy.get_open_dialog().find('.btn-primary').click();
		cy.wait('@upload_file').its('response.body.message')
			.should('have.property', 'file_url', '/private/files/example.json');
		cy.get('.modal:visible').should('not.exist');
	});

	it('should accept web links', () => {
		open_upload_dialog();

		cy.get_open_dialog().find('a:contains("web link")').click();
		cy.get_open_dialog().find('.file-web-link input').type('https://github.com');
		cy.server();
		cy.route('POST', '/api/method/upload_file').as('upload_file');
		cy.get_open_dialog().find('.btn-primary').click();
		cy.wait('@upload_file').its('response.body.message')
			.should('have.property', 'file_url', 'https://github.com');
		cy.get('.modal:visible').should('not.exist');
	});
});
