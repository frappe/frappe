context('Grid Keyboard Shortcut', () => {
	let total_count = 0;
	beforeEach(() => {
		cy.login();
		cy.visit('/app/doctype/User');
	});
	before(() => {
		cy.login();
		cy.visit('/app/doctype/User');
		return cy.window().its('frappe').then(frappe => {
			frappe.db.count('DocField', {
				filters: {
					'parent': 'User', 'parentfield': 'fields', 'parenttype': 'DocType'
				}
			}).then((r) => {
				total_count = r;
			});
		});
	});
	it('Insert new row at the end', () => {
		cy.add_new_row_in_grid('{ctrl}{shift}{downarrow}', (cy, total_count) => {
			cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', `${total_count+1}`);
		}, total_count);
	});
	it('Insert new row at the top', () => {
		cy.add_new_row_in_grid('{ctrl}{shift}{uparrow}', (cy) => {
			cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '1');
		});
	});
	it('Insert new row below', () => {
		cy.add_new_row_in_grid('{ctrl}{downarrow}', (cy) => {
			cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '2');
		});
	});
	it('Insert new row above', () => {
		cy.add_new_row_in_grid('{ctrl}{uparrow}', (cy) => {
			cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '1');
		});
	});
});

Cypress.Commands.add('add_new_row_in_grid', (shortcut_keys, callbackFn, total_count) => {
	cy.get('.frappe-control[data-fieldname="fields"]').as('table');
	cy.get('@table').find('.grid-body .col-xs-2').first().click();
	cy.get('@table').find('.grid-body .col-xs-2')
		.first().type(shortcut_keys);

	callbackFn(cy, total_count);
});