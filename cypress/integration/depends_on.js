context('Depends On', () => {
	before(() => {
		cy.login();
		cy.visit('/desk#workspace/Website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call('frappe.tests.ui_test_helpers.create_doctype', {
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
				]
			});
		});
	});
	it('should set the field as mandatory depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.fill_field('test_field', 'Some Value');
		cy.get('button.primary-action').contains('Save').click();
		cy.get('.msgprint-dialog .modal-title').contains('Missing Fields').should('be.visible');
		cy.get('body').click();
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
	it('should display the field depending on other fields value', () => {
		cy.new_form('Test Depends On');
		cy.get('.control-input [data-fieldname="display_dependant_field"]').should('not.be.visible');
		cy.get('.control-input [data-fieldname="test_field"]').clear();
		cy.fill_field('test_field', 'Value');
		cy.get('body').click();
		cy.get('.control-input [data-fieldname="display_dependant_field"]').should('be.visible');
	});
});
