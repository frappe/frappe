context('List View', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.xcall("frappe.tests.ui_test_helpers.setup_workflow");
		});
	});
	it('enables "Actions" button', () => {
		const actions = ['Approve', 'Reject', 'Edit', 'Assign To', 'Apply Assignment Rule', 'Add Tags', 'Print', 'Delete'];
		cy.go_to_list('ToDo');
		cy.get('.list-row-container:contains("Pending") .list-row-checkbox').click({ multiple: true, force: true });
		cy.get('.actions-btn-group button').contains('Actions').should('be.visible').click();
		cy.get('.dropdown-menu li:visible .dropdown-item').should('have.length', 8).each((el, index) => {
			cy.wrap(el).contains(actions[index]);
		}).then((elements) => {
			cy.intercept({
				method: 'POST',
				url: 'api/method/frappe.model.workflow.bulk_workflow_approval'
			}).as('bulk-approval');
			cy.intercept({
				method: 'POST',
				url: 'api/method/frappe.desk.reportview.get'
			}).as('real-time-update');
			cy.wrap(elements).contains('Approve').click();
			cy.wait(['@bulk-approval', '@real-time-update']);
			cy.hide_dialog();
			cy.clear_filters();
			cy.get('.list-row-container:visible').should('contain', 'Approved');
		});
	});
});

