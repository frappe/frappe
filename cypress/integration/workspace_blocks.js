context('Workspace Blocks', () => {
	before(() => {
		cy.login();
		cy.visit('/app');
	});

	it('Create Test Page', () => {
		cy.intercept({
			method: 'POST',
			url: 'api/method/frappe.desk.doctype.workspace.workspace.new_page'
		}).as('new_page');

		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.custom-actions button[data-label="Create%20Workspace"]').click();
		cy.fill_field('title', 'Test Block Page', 'Data');
		cy.fill_field('icon', 'edit', 'Icon');
		cy.get_open_dialog().find('.modal-header').click();
		cy.get_open_dialog().find('.btn-primary').click();

		// check if sidebar item is added in private section
		cy.get('.sidebar-item-container[item-name="Test Block Page"]').should('have.attr', 'item-public', '0');

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Block Page"]').should('have.attr', 'item-public', '0');

		cy.wait('@new_page');
	});

	it('Quick List Block', () => {
		cy.create_records([
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 1',
				status: 'Open'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 2',
				status: 'Open'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 3',
				status: 'Open'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 4',
				status: 'Open'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 5',
				status: 'Closed'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 6',
				status: 'Closed'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 7',
				status: 'Closed'
			},
			{
				doctype: 'ToDo',
				description: 'Quick List ToDo 8',
				status: 'Closed'
			}
		]);

		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.standard-actions .btn-secondary[data-label=Edit]').click();

		// test quick list creation
		cy.get('.ce-block').first().click({force: true}).type('{enter}');
		cy.get('.block-list-container .block-list-item').contains('Quick List').click();

		cy.get_open_dialog().find('.modal-header').click();

		cy.fill_field('document_type', 'ToDo', 'Link').blur();
		cy.fill_field('label', 'ToDo', 'Data').blur();

		cy.get_open_dialog().find('.filter-edit-area').should('contain', 'No filters selected');
		cy.get_open_dialog().find('.filter-area .add-filter').click();

		cy.get_open_dialog().find('.fieldname-select-area input').type('Status{enter}').blur();
		cy.get_open_dialog().find('select.input-with-feedback').select('Open');

		cy.get_open_dialog().find('.modal-header').click();
		cy.get_open_dialog().find('.btn-primary').click();

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();


		cy.get('.codex-editor__redactor .ce-block');

		cy.get('.ce-block .quick-list-widget-box').first().as('todo-quick-list');

		cy.get('@todo-quick-list').find('.quick-list-item .status').should('contain', 'Open');

		// test filter-list
		cy.get('@todo-quick-list').find('.widget-control .filter-list').click();

		cy.get_open_dialog().find('select.input-with-feedback').select('Closed');
		cy.get_open_dialog().find('.modal-header').click();
		cy.get_open_dialog().find('.btn-primary').click();

		cy.get('@todo-quick-list').find('.quick-list-item .status').should('contain', 'Closed');


		// test refresh-list
		cy.intercept({
			method: 'POST',
			url: 'api/method/frappe.desk.reportview.get'
		}).as('refresh-list');

		cy.get('@todo-quick-list').find('.widget-control .refresh-list').click();
		cy.wait('@refresh-list');


		// test add-new
		cy.get('@todo-quick-list').find('.widget-control .add-new').click();
		cy.url().should('include', `/todo/new-todo-1`);
		cy.go('back');


		// test quick-list-item
		cy.get('@todo-quick-list').find('.quick-list-item .title')
			.first()
			.invoke('attr', 'title')
			.then(title => {
				cy.get('@todo-quick-list').find('.quick-list-item').contains(title).click();
				cy.get_field('description', 'Text Editor').should('contain', title);
			});
		cy.go('back');


		// test see-all
		cy.get('@todo-quick-list').find('.widget-footer .see-all').click();

		cy.get('.standard-filter-section select[data-fieldname="status"]')
			.invoke('val')
			.should('eq', 'Open');
		cy.go('back');
	});

});