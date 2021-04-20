context('Control Link', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	beforeEach(() => {
		cy.visit('/app/website');
		cy.create_records({
			doctype: 'ToDo',
			description: 'this is a test todo for link'
		}).as('todos');
	});

	function get_dialog_with_link() {
		return cy.dialog({
			title: 'Link',
			fields: [
				{
					'label': 'Select ToDo',
					'fieldname': 'link',
					'fieldtype': 'Link',
					'options': 'ToDo'
				}
			]
		});
	}

	it('should set the valid value', () => {
		get_dialog_with_link().as('dialog');

		cy.intercept('POST', '/api/method/frappe.desk.search.search_link').as('search_link');

		cy.get('.frappe-control[data-fieldname=link] input').focus().as('input');
		cy.wait('@search_link');
		cy.get('@input').type('todo for link', { delay: 200 });
		cy.wait('@search_link');
		cy.get('.frappe-control[data-fieldname=link] ul').should('be.visible');
		cy.get('.frappe-control[data-fieldname=link] input').type('{enter}', { delay: 100 });
		cy.get('.frappe-control[data-fieldname=link] input').blur();
		cy.get('@dialog').then(dialog => {
			cy.get('@todos').then(todos => {
				let value = dialog.get_value('link');
				expect(value).to.eq(todos[0]);
			});
		});
	});

	it('should unset invalid value', () => {
		get_dialog_with_link().as('dialog');

		cy.intercept('GET', '/api/method/frappe.desk.form.utils.validate_link*').as('validate_link');

		cy.get('.frappe-control[data-fieldname=link] input')
			.type('invalid value', { delay: 100 })
			.blur();
		cy.wait('@validate_link');
		cy.get('.frappe-control[data-fieldname=link] input').should('have.value', '');
	});

	it('should route to form on arrow click', () => {
		get_dialog_with_link().as('dialog');

		cy.intercept('GET', '/api/method/frappe.desk.form.utils.validate_link*').as('validate_link');
		cy.intercept('POST', '/api/method/frappe.desk.search.search_link').as('search_link');

		cy.get('@todos').then(todos => {
			cy.get('.frappe-control[data-fieldname=link] input').as('input');
			cy.get('@input').focus();
			cy.wait('@search_link');
			cy.get('@input').type(todos[0]).blur();
			cy.wait('@validate_link');
			cy.get('@input').focus();
			cy.get('.frappe-control[data-fieldname=link] .link-btn')
				.should('be.visible')
				.click();
			cy.location('pathname').should('eq', `/app/todo/${todos[0]}`);
		});
	});
});
