context('Folder Navigation', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/file');
	});

	it('Adding Folders', () => {
		//Adding filter to go into the home folder
		cy.get('.filter-selector > .btn').findByText('1 filter').click();
		cy.findByRole('button', {name: 'Clear Filters'}).click();
		cy.get('.filter-action-buttons > .text-muted').findByText('+ Add a Filter').click();
		cy.get('.fieldname-select-area > .awesomplete > .form-control').type('Fol{enter}');
		cy.get('.filter-field > .form-group > .link-field > .awesomplete > .input-with-feedback').type('Home{enter}');
		cy.get('.filter-action-buttons > div > .btn-primary').findByText('Apply Filters').click();

		//Adding folder (Test Folder)
		cy.get('.menu-btn-group > .btn').click();
		cy.get('.menu-btn-group [data-label="New Folder"]').click();
		cy.get('form > [data-fieldname="value"]').type('Test Folder');
		cy.findByRole('button', {name: 'Create'}).click();   
	});

	it('Navigating the nested folders, checking if the URL formed is correct, checking if the added content in the child folder is correct', () => {
		//Navigating inside the Attachments folder
		cy.get('[title="Attachments"] > span').click();

		//To check if the URL formed after visiting the attachments folder is correct
		cy.location('pathname').should('eq', '/app/file/view/home/Attachments');
		cy.visit('/app/file/view/home/Attachments');

		//Adding folder inside the attachments folder
		cy.get('.menu-btn-group > .btn').click();
		cy.get('.menu-btn-group [data-label="New Folder"]').click();
		cy.get('form > [data-fieldname="value"]').type('Test Folder');
		cy.findByRole('button', {name: 'Create'}).click();

		//Navigating inside the added folder in the Attachments folder
		cy.get('[title="Test Folder"] > span').click();

		//To check if the URL is correct after visiting the Test Folder
		cy.location('pathname').should('eq', '/app/file/view/home/Attachments/Test%20Folder');
		cy.visit('/app/file/view/home/Attachments/Test%20Folder');

		//Adding a file inside the Test Folder
		cy.findByRole('button', {name: 'Add File'}).eq(0).click({force: true});
		cy.get('.file-uploader').findByText('Link').click();
		cy.get('.input-group > .form-control').type('https://wallpaperplay.com/walls/full/8/2/b/72402.jpg');
		cy.findByRole('button', {name: 'Upload'}).click();

		//To check if the added file is present in the Test Folder
		cy.get('span.level-item > span').should('contain', 'Test Folder');
		cy.get('.list-row-container').eq(0).should('contain.text', '72402.jpg');
		cy.get('.list-row-checkbox').eq(0).click();

		//Deleting the added file from the Test folder
		cy.findByRole('button', {name: 'Actions'}).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.wait(700);
		cy.findByRole('button', {name: 'Yes'}).click();
		cy.wait(700);

		//Deleting the Test Folder
		cy.visit('/app/file/view/home/Attachments');
		cy.get('.list-row-checkbox').eq(0).click();
		cy.findByRole('button', {name: 'Actions'}).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();  
		cy.findByRole('button', {name: 'Yes'}).click();
	});

	it('Deleting Test Folder from the home', () => {
	//Deleting the Test Folder added in the home directory
		cy.visit('/app/file/view/home');
		cy.get('.level-left > .list-subject > .file-select >.list-row-checkbox').eq(0).click({force: true, delay: 500});
		cy.findByRole('button', {name: 'Actions'}).click();
		cy.get('.actions-btn-group [data-label="Delete"]').click();
		cy.findByRole('button', {name: 'Yes'}).click();
	});
}); 
