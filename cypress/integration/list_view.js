context('List View', () => {
	before(() => {
		cy.login();
		cy.visit('/desk');
		cy.window().its('frappe').then(frappe => {
			frappe.call("frappe.tests.ui_test_helpers.setup_workflow");
		});
		cy.clear_cache();
	});
	it('enables "Actions" button', () => {
		const actions = ['Approve', 'Reject', 'Edit', 'Assign To', 'Print','Delete'];
		cy.go_to_list('ToDo');
		cy.get('.level-item.list-row-checkbox.hidden-xs').click({ multiple: true, force: true });
		cy.get('.btn.btn-primary.btn-sm.dropdown-toggle').contains('Actions').should('be.visible').click();
		cy.get('.dropdown-menu li:visible').should('have.length', 6).each((el, index) => {
			cy.wrap(el).contains(actions[index]);
		}).then((elements) => {
			cy.server();
			cy.route({
				method: 'POST',
				url:'api/method/frappe.model.workflow.bulk_workflow_approval'
			}).as('bulk-approval');
			cy.route({
				method: 'GET',
				url:'api/method/frappe.desk.reportview.get*'
			}).as('update-list');
			cy.wrap(elements).contains('Approve').click();
			cy.wait(['@bulk-approval', '@update-list']);
			cy.get('.list-row-container:visible').should('contain', 'Approved');
		});
	});
});

