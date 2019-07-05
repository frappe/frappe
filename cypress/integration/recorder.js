context('Recorder', () => {
	before(() => {
		cy.login();
	});

	it('Navigate to Recorder', () => {
		cy.visit('/desk');
		cy.awesomebar('recorder');
		cy.get('h1').should('contain', 'Recorder');
		cy.location('hash').should('eq', '#recorder');
	});

	it('Recorder Empty State', () => {
		cy.visit('/desk#recorder');
		cy.get('.title-text').should('contain', 'Recorder');

		cy.get('.indicator').should('contain', 'Inactive').should('have.class', 'red');

		cy.get('.primary-action').should('contain', 'Start');
		cy.get('.btn-secondary').should('contain', 'Clear');

		cy.get('.msg-box').should('contain', 'Inactive');
		cy.get('.msg-box .btn-primary').should('contain', 'Start Recording');
	});

	it('Recorder Start', () => {
		cy.visit('/desk#recorder');
		cy.get('.primary-action').should('contain', 'Start').click();
		cy.get('.indicator').should('contain', 'Active').should('have.class', 'green');

		cy.get('.msg-box').should('contain', 'No Requests');

		cy.server();
		cy.visit('/desk#List/DocType/List');
		cy.route('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/desk#recorder');
		cy.get('.title-text').should('contain', 'Recorder');
		cy.get('.result-list').should('contain', '/api/method/frappe.desk.reportview.get');

		cy.get('#page-recorder .primary-action').should('contain', 'Stop').click();
		cy.get('#page-recorder .btn-secondary').should('contain', 'Clear').click();
		cy.get('.msg-box').should('contain', 'Inactive');
	});

	it('Recorder View Request', () => {
		cy.visit('/desk#recorder');
		cy.get('.primary-action').should('contain', 'Start').click();

		cy.server();
		cy.visit('/desk#List/DocType/List');
		cy.route('POST', '/api/method/frappe.desk.reportview.get').as('list_refresh');
		cy.wait('@list_refresh');

		cy.get('.title-text').should('contain', 'DocType');
		cy.get('.list-count').should('contain', '20 of ');

		cy.visit('/desk#recorder');

		cy.contains('.list-row-container span', 'frappe.desk.reportview.get').click();

		cy.location('hash').should('contain', '#recorder/request/');
		cy.get('form').should('contain', 'frappe.desk.reportview.get');

		cy.get('#page-recorder .primary-action').should('contain', 'Stop').click();
		cy.get('#page-recorder .btn-secondary').should('contain', 'Clear').click();
		cy.location('hash').should('eq', '#recorder');
	});
});