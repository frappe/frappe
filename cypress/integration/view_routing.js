context('View', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.xcall("frappe.tests.ui_test_helpers.setup_default_view");
		});
	});

	it('Re-route to default view', () => {
		cy.go_to_list('Event');
		cy.location('pathname').should('eq', `/app/event/view/report`);
	});
});
