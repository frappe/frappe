// TODO: Enable this again
// currently this is flaky possibly because of different timezone in CI

// context('Datetime Field Validation', () => {
// 	before(() => {
// 		cy.login();
// 		cy.visit('/app/communication');
// 	});

// 	it('datetime field form validation', () => {
// 		// validating datetime field value when value is set from backend and get validated on form load.
// 		cy.window().its('frappe').then(frappe => {
// 			return frappe.xcall("frappe.tests.ui_test_helpers.create_communication_record");
// 		}).then(doc => {
// 			cy.visit(`/app/communication/${doc.name}`);
// 			cy.get('.indicator-pill').should('contain', 'Open').should('have.class', 'red');
// 		});
// 	});
// });
