context('List View', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.test_utils.setup_workflow");
			cy.reload();
		});
	});
	it('Bulk Workflow Action', () => {
		cy.go_to_list('ToDo');
		cy.get('.level-item.list-row-checkbox.hidden-xs').click({ multiple: true, force: true });
	});
});

