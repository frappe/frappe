context('View', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	it('Re-route to default view', () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {force_reroute: true}).then(() => {
			cy.go_to_list('Event');
			cy.wait(500);
			cy.location('pathname').should('eq', `/app/event/view/report`);
		});
	});

	it('Route to default view from app/{doctype}', () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {}).then(() => {
			cy.visit('/app/event/view');
			cy.wait(500);
			cy.location('pathname').should('eq', `/app/event/view/report`);
		});
	});

	it('Route to default view from app/{doctype}/view', () => {
		cy.call("frappe.tests.ui_test_helpers.setup_default_view", {force_reroute: true}).then(() => {
			cy.visit('/app/event/view');
			cy.wait(500);
			cy.location('pathname').should('eq', `/app/event/view/report`);
		});
	});
});
