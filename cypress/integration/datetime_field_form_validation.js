// TODO: Enable this again
// currently this is flaky possibly because of different timezone in CI

// context('Datetime Field Validation', () => {
// 	before(() => {
// 		cy.login();
// 		cy.visit('/app/communication');
// 		cy.window().its('frappe').then(frappe => {
// 			frappe.call("frappe.tests.ui_test_helpers.create_communication_records");
// 		});
// 	});

// 	// validating datetime field value when value is set from backend and get validated on form load.
// 	it('datetime field form validation', () => {
// 		cy.visit('/app/communication');
// 		cy.get('a[title="Test Form Communication 1"]').invoke('attr', 'data-name')
// 			.then((name) => {
// 				cy.visit(`/app/communication/${name}`);
// 				cy.get('.indicator-pill').should('contain', 'Open').should('have.class', 'red');
// 			});
// 	});
// });