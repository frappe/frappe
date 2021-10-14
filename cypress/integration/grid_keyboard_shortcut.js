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
            })
		});
	});
	it('Insert new row at the end', () => {
        cy.wait(100);
        cy.get('.frappe-control[data-fieldname="fields"]').as('table');
        cy.get('.grid-body .grid-row').find('.col-xs-2').first().click()
        cy.get('.grid-body .grid-row').find('.col-xs-2')
            .first().type('{ctrl}{shift}{downarrow}').should('be.visible')
        cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', `${total_count+1}`);
    });
    it('Insert new row at the top', () => {
        cy.wait(100);
        cy.get('.frappe-control[data-fieldname="fields"]').as('table');
        cy.get('.grid-body .grid-row').find('.col-xs-2').first().click()
        cy.get('.grid-body .grid-row').find('.col-xs-2')
            .first().type('{ctrl}{shift}{uparrow}').should('be.visible')
        cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '1');
    });
    it('Insert new row below', () => {
        cy.wait(100);
        cy.get('.frappe-control[data-fieldname="fields"]').as('table');
        cy.get('.grid-body .grid-row').find('.col-xs-2').first().click()
        cy.get('.grid-body .grid-row').find('.col-xs-2')
            .first().type('{ctrl}{downarrow}').should('be.visible')
        cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '2');
	});
    it('Insert new row above', () => {
        cy.wait(100);
        cy.get('.frappe-control[data-fieldname="fields"]').as('table');
        cy.get('.grid-body .grid-row').find('.col-xs-2').first().click()
        cy.get('.grid-body .grid-row').find('.col-xs-2')
            .first().type('{ctrl}{uparrow}').should('be.visible')
        cy.get('[data-name="new-docfield-1"]').should('have.attr', 'data-idx', '1');
    });
});