context('Dynamic Link', () => {
	before(() => {
		cy.login();
		cy.visit('/app/doctype');
			return cy.window().its('frappe').then(frappe => {
				return frappe.xcall('frappe.tests.ui_test_helpers.create_doctype', {
				name: 'Test Dynamic Link',
					fields: [
						{
						"label": "Document Type",
						"fieldname": "doc_type",
						"fieldtype": "Link",
						"options": "DocType",
						"in_list_view": 1,
						},
						{
						"label": "Document ID",
						"fieldname": "doc_id",
						"fieldtype": "Dynamic Link",
						"options": "doc_type",
						"in_list_view": 1,
						},
					]
				});
			});
	});
	it('Creating a dynamic link and verifying it', () => {
		cy.new_form('Test Dynamic Link');
		cy.get('form > [data-fieldname="doc_type"]').type('User');
		cy.get('form > [data-fieldname="doc_id"]').click();
		cy.get('[id="awesomplete_list_4"]').its('length').should('be.gte', 0);

	});
});
