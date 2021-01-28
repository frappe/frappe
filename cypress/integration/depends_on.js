context('Depends On', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.xcall('frappe.tests.ui_test_helpers.create_child_doctype', {
				name: 'Child Test Depends On',
				fields: [
					{
						"label": "Child Test Field",
						"fieldname": "child_test_field",
						"fieldtype": "Data",
						"in_list_view": 1,
					},
					{
						"label": "Child Dependant Field",
						"fieldname": "child_dependant_field",
						"fieldtype": "Data",
						"in_list_view": 1,
					},
					{
						"label": "Child Display Dependant Field",
						"fieldname": "child_display_dependant_field",
						"fieldtype": "Data",
						"in_list_view": 1,
					},
				]
			});
		}).then(frappe => {
			return frappe.xcall('frappe.tests.ui_test_helpers.create_doctype', {
				name: 'Test Depends On',
				fields: [
					{
						"label": "Test Field",
						"fieldname": "test_field",
						"fieldtype": "Data",
					},
					{
						"label": "Dependant Field",
						"fieldname": "dependant_field",
						"fieldtype": "Data",
						"mandatory_depends_on": "eval:doc.test_field=='Some Value'",
						"read_only_depends_on": "eval:doc.test_field=='Some Other Value'",
					},
					{
						"label": "Display Dependant Field",
						"fieldname": "display_dependant_field",
						"fieldtype": "Data",
						'depends_on': "eval:doc.test_field=='Value'"
					},
					{
						"label": "Child Test Depends On Field",
						"fieldname": "child_test_depends_on_field",
						"fieldtype": "Table",
						'read_only_depends_on': "eval:doc.test_field=='Some Other Value'",
						'options': "Child Test Depends On"
					},
				]
			});
		});
	});
	it('should set the field as mandatory depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.fill_field('test_field', 'Some Value');
		cy.get('button.primary-action').contains('Save').click();
		cy.get('.msgprint-dialog .modal-title').contains('Missing Fields').should('be.visible');
		cy.hide_dialog();
		cy.fill_field('test_field', 'Random value');
		cy.get('button.primary-action').contains('Save').click();
		cy.get('.msgprint-dialog .modal-title').contains('Missing Fields').should('not.be.visible');
	});
	it('should set the field as read only depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.fill_field('dependant_field', 'Some Value');
		cy.fill_field('test_field', 'Some Other Value');
		cy.get('body').click();
		cy.get('.control-input [data-fieldname="dependant_field"]').should('be.disabled');
		cy.fill_field('test_field', 'Random Value');
		cy.get('body').click();
		cy.get('.control-input [data-fieldname="dependant_field"]').should('not.be.disabled');
	});
	it('should set the table and its fields as read only depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.fill_field('dependant_field', 'Some Value');
		//cy.fill_field('test_field', 'Some Other Value');
		cy.get('.frappe-control[data-fieldname="child_test_depends_on_field"]').as('table');
		cy.get('@table').find('button.grid-add-row').click();
		cy.get('@table').find('[data-idx="1"]').as('row1');
		cy.get('@row1').find('.btn-open-row').click();
		cy.get('@row1').find('.form-in-grid').as('row1-form_in_grid');
		//cy.get('@row1-form_in_grid').find('')
		cy.fill_table_field('child_test_depends_on_field', '1', 'child_test_field', 'Some Value');
		cy.fill_table_field('child_test_depends_on_field', '1', 'child_dependant_field', 'Some Other Value');

		cy.get('@row1-form_in_grid').find('.grid-collapse-row').click();

		// set the table to read-only
		cy.fill_field('test_field', 'Some Other Value');

		// grid row form fields should be read-only
		cy.get('@row1').find('.btn-open-row').click();

		cy.get('@row1-form_in_grid').find('.control-input [data-fieldname="child_test_field"]').should('be.disabled');
		cy.get('@row1-form_in_grid').find('.control-input [data-fieldname="child_dependant_field"]').should('be.disabled');
	});
	it('should display the field depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.get('.control-input [data-fieldname="display_dependant_field"]').should('not.be.visible');
		cy.get('.control-input [data-fieldname="test_field"]').clear();
		cy.fill_field('test_field', 'Value');
		cy.get('body').click();
		cy.get('.control-input [data-fieldname="display_dependant_field"]').should('be.visible');
	});
});
