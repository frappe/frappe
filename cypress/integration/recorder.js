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

	it('Recorder Empty State', () => {
		cy.findByTitle('Recorder').should('exist');

		cy.get('.indicator-pill').should('contain', 'Inactive').should('have.class', 'red');

		cy.findByRole('button', {name: 'Start'}).should('exist');
		cy.findByRole('button', {name: 'Clear'}).should('exist');

		cy.get('.msg-box').should('contain', 'Inactive');
		cy.findByRole('button', {name: 'Start Recording'}).should('exist');
	});

	it('Recorder Start', () => {
		cy.findByRole('button', {name: 'Start'}).click();
		cy.get('.indicator-pill').should('contain', 'Active').should('have.class', 'green');

		cy.get('.msg-box').should('contain', 'No Requests');

		cy.visit('/app/List/DocType/List');
		cy.intercept('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/app/recorder');
		cy.findByTitle('Recorder').should('exist');
		cy.get('.result-list').should('contain', '/api/method/frappe.desk.reportview.get');
	});

	it('Recorder View Request', () => {
		cy.findByRole('button', {name: 'Start'}).click();

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
