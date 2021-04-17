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
		cy.fill_field('description', 'this is a test todo', 'Text Editor');
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
		let valid_email = 'user@email.com';
		let expectBackgroundColor = 'rgb(255, 245, 245)';

		cy.visit('/app/contact/new');
		cy.get('.frappe-control[data-fieldname="email_ids"]').as('table');
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('@table').find('[data-idx="1"]').as('row1');
		cy.get('@table').find('[data-idx="2"]').as('row2');
		cy.get('@row1').click();
		cy.get('@row1').find('input.input-with-feedback.form-control').as('email_input1');

		cy.get('@email_input1').type(website_input, { waitForAnimations: false });
		cy.fill_field('company_name', 'Test Company');

		cy.get('@row2').click();
		cy.get('@row2').find('input.input-with-feedback.form-control').as('email_input2');
		cy.get('@email_input2').type(valid_email, { waitForAnimations: false });

		cy.get('@row1').click();
		cy.get('@email_input1').should($div => {
			const style = window.getComputedStyle($div[0]);
			expect(style.backgroundColor).to.equal(expectBackgroundColor);
		});
		cy.get('@email_input1').should('have.class', 'invalid');

		cy.get('@row2').click();
		cy.get('@email_input2').should('not.have.class', 'invalid');
	});
});
