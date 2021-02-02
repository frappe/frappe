context('Form', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_contact_records");
		});
	});
	it('create a new form', () => {
		cy.visit('/app/todo/new');
		cy.fill_field('description', 'this is a test todo', 'Text Editor').blur();
		cy.wait(300);
		cy.get('.page-title').should('contain', 'Not Saved');
		cy.intercept({
			method: 'POST',
			url: 'api/method/frappe.desk.form.save.savedocs'
		}).as('form_save');
		cy.get('.primary-action').click();
		cy.wait('@form_save').its('response.statusCode').should('eq', 200);
		cy.visit('/app/todo');
		cy.get('.title-text').should('be.visible').and('contain', 'To Do');
		cy.get('.list-row').should('contain', 'this is a test todo');
	});
	it('navigates between documents with child table list filters applied', () => {
		cy.visit('/app/contact');
		cy.add_filter();
		cy.get('.filter-field .input-with-feedback.form-control').type('123', { force: true });
		cy.get('.filter-popover .apply-filters').click({ force: true });
		cy.visit('/app/contact/Test Form Contact 3');
		cy.get('.prev-doc').should('be.visible').click();
		cy.get('.msgprint-dialog .modal-body').contains('No further records').should('be.visible');
		cy.hide_dialog();
		cy.get('.next-doc').click();
		cy.wait(200);
		cy.hide_dialog();
		cy.contains('Test Form Contact 2').should('not.exist');
		cy.get('.title-text').should('contain', 'Test Form Contact 3');
		// clear filters
		cy.visit('/app/contact');
		cy.clear_filters();
	});
	it('validates behaviour of Data options validations in child table', () => {
		// test email validations for set_invalid controller
		let website_input = 'website.in';
		let expectBackgroundColor = 'rgb(255, 245, 245)';

		cy.visit('/app/contact/new');
		cy.get('.frappe-control[data-fieldname="email_ids"]').as('table');
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('.grid-body .rows [data-fieldname="email_id"]').click();
		cy.get('@table').find('input.input-with-feedback.form-control').as('email_input');
		cy.get('@email_input').type(website_input, { waitForAnimations: false });
		cy.fill_field('company_name', 'Test Company');
		cy.get('@email_input').should($div => {
			const style = window.getComputedStyle($div[0]);
			expect(style.backgroundColor).to.equal(expectBackgroundColor);
		});
	});
});
