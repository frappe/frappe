context('Form', () => {
	before(() => {
		cy.login();
		cy.visit('/desk#workspace/Website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_contact_records");
		});
	});
	it('create a new form', () => {
		cy.visit('/desk#Form/ToDo/New ToDo 1');
		cy.fill_field('description', 'this is a test todo', 'Text Editor').blur();
		cy.wait(300);
		cy.get('.page-title').should('contain', 'Not Saved');
		cy.server();
		cy.route({
			method: 'POST',
			url: 'api/method/frappe.desk.form.save.savedocs'
		}).as('form_save');
		cy.get('.primary-action').click();
		cy.wait('@form_save').its('status').should('eq', 200);
		cy.visit('/desk#List/ToDo');
		cy.location('hash').should('eq', '#List/ToDo/List');
		cy.get('h1').should('be.visible').and('contain', 'To Do');
		cy.get('.list-row').should('contain', 'this is a test todo');
	});
	it('navigates between documents with child table list filters applied', () => {
		cy.visit('/desk#List/Contact');
		cy.location('hash').should('eq', '#List/Contact/List');
		cy.get('.tag-filters-area .btn:contains("Add Filter")').click();
		cy.get('.fieldname-select-area').should('exist');
		cy.get('.fieldname-select-area input').type('Number{enter}', { force: true });
		cy.get('.filter-field .input-with-feedback.form-control').type('123', { force: true });
		cy.get('.filter-box .btn:contains("Apply")').click({ force: true });
		cy.visit('/desk#Form/Contact/Test Form Contact 3');
		cy.get('.prev-doc').should('be.visible').click();
		cy.get('.msgprint-dialog .modal-body').contains('No further records').should('be.visible');
		cy.get('.btn-modal-close:visible').click();
		cy.get('.next-doc').click();
		cy.wait(200);
		cy.contains('Test Form Contact 2').should('not.exist');
		cy.get('.page-title .title-text').should('contain', 'Test Form Contact 1');
		// clear filters
		cy.window().its('frappe').then((frappe) => {
			let list_view = frappe.get_list_view('Contact');
			list_view.filter_area.filter_list.clear_filters();
		});
	});
	it('validates behaviour of Data options validations in child table', () => {
		// test email validations for set_invalid controller
		let website_input = 'website.in';
		let expectBackgroundColor = 'rgb(255, 220, 220)';

		cy.visit('/desk#Form/Contact/New Contact 1');
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
