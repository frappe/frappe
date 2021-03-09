context('Recorder', () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit('/app/recorder');
		return cy.window().its('frappe').then(frappe => {
			// reset recorder
			return frappe.xcall("frappe.recorder.stop").then(() => {
				return frappe.xcall("frappe.recorder.delete");
			});
		});
	});

	it('Navigate to Recorder', () => {
		cy.visit('/app');
		cy.awesomebar('recorder');
		cy.get('h3').should('contain', 'Recorder');
		cy.url().should('include', '/recorder/detail');
	});

	it('Recorder Empty State', () => {
		cy.get('.title-text').should('contain', 'Recorder');

		cy.get('.indicator-pill').should('contain', 'Inactive').should('have.class', 'red');

		cy.get('.primary-action').should('contain', 'Start');
		cy.get('.btn-secondary').should('contain', 'Clear');

		cy.get('.msg-box').should('contain', 'Inactive');
		cy.get('.msg-box .btn-primary').should('contain', 'Start Recording');
	});

	it('Recorder Start', () => {
		cy.get('.primary-action').should('contain', 'Start').click();
		cy.get('.indicator-pill').should('contain', 'Active').should('have.class', 'green');

		cy.get('.msg-box').should('contain', 'No Requests');

		cy.visit('/app/List/DocType/List');
		cy.intercept('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/app/recorder');
		cy.get('.title-text').should('contain', 'Recorder');
		cy.get('.result-list').should('contain', '/api/method/frappe.desk.reportview.get');
	});

	it.only('Recorder View Request', () => {
		cy.get('.primary-action').should('contain', 'Start').click();

		cy.visit('/app/List/DocType/List');
		cy.intercept('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/app/recorder');

		cy.get('.list-row-container span').contains('/api/method/frappe').click();

		cy.url().should('include', '/recorder/request');
		cy.get('form').should('contain', '/api/method/frappe');
	});
});
