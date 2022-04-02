context("Form Sidebar", () => {
	before(() => {
		cy.visit('http://resilient_test:8000/');
		cy.login("administrator", "samx6730");
		cy.visit('/app/todo');

	});
	
	it("Test for checking Save Templates on doctypes", () => {
		cy.insert_doc('ToDo', {
			'__newname': 'TEST#123', 
			'description': 'Test this', 
			'ignore_duplicate': true
		});
		cy.visit('/app/todo/TEST%23123');
		cy.findByPlaceholderText('Template Name')
			.type('Test Quotation{enter}')
			.blur();
		cy.get('button[data-name="Test Quotation"]').click();
		cy.intercept('POST', '/api/method/frappe.desk.form.save.savedocs').as('save_form');
		// trigger save
		cy.get('.primary-action').click();
		cy.wait('@save_form').its('response.statusCode').should('eq', 200);
	});

	it("Show saved Templates", () => {
		cy.get_list("Quotation").as('saved-template')
		cy.get('.form-template > .sidebar-action > a').click()
		cy.get('[data-name="Test Quotation"]').should('be.visible');
	})
});