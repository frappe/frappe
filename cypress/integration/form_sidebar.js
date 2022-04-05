context("Form Sidebar", () => {
	before(() => {
		cy.login();
		cy.visit('/app/todo');

	});

	function show_saved_templates() {
		cy.get_list("ToDo")
			.its('data')
			.then(data => expect(data.length).to.be.at.least(1));

		cy.get('.form-template > .sidebar-action > a').click();
		cy.get('[data-name="Test ToDo"]').should('be.visible');
	}

	function use_saved_templates() {
		cy.get('button[data-name="Test ToDo"]').click();
		cy.intercept('POST', '/api/method/frappe.desk.form.save.savedocs').as('save_form');
		// trigger save
		cy.get('.primary-action').click();
		cy.wait('@save_form').its('response.statusCode').should('eq', 200);
	}
	
	it("Test to save templates for doctypes", () => {
		cy.insert_doc('ToDo', {
			'__newname': 'TEST#123', 
			'description': 'This ToDo is for Cypress Testing', 
			'ignore_duplicate': true
		});
		cy.visit('/app/todo/TEST%23123');
		cy.findByPlaceholderText('Template Name')
			.type('Test ToDo{enter}')
			.blur();
	});

	it("Show saved Templates", () => {
		show_saved_templates();
	});

	it("Use saved template to update existiong doctype", () => {
		use_saved_templates();
	});

	it("Use saved templates in new docs", () => {
		cy.new_form("ToDo");
		show_saved_templates();
		use_saved_templates();
	});
});