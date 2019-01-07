context('Login', () => {
	beforeEach(() => {
		cy.request('/api/method/logout');
		cy.visit('/login');
		cy.location().should('be', '/login');
	});

	it('greets with login screen', () => {
		cy.get('.page-card-head').contains('Login');
	});

	it('validates password', () => {
		cy.get('#login_email').type('Administrator');
		cy.get('.btn-login').click();
		cy.location('pathname').should('eq', '/login');
	});

	it('validates email', () => {
		cy.get('#login_password').type('qwe');
		cy.get('.btn-login').click();
		cy.location('pathname').should('eq', '/login');
	});

	it('logs in using correct credentials', () => {
		cy.get('#login_email').type('Administrator');
		cy.get('#login_password').type('qwe');

		cy.get('.btn-login').click();
		cy.location('pathname').should('eq', '/desk');
		cy.window().its('frappe.session.user').should('eq', 'Administrator');
	});

	it('shows invalid login if incorrect credentials', () => {
		cy.get('#login_email').type('Administrator');
		cy.get('#login_password').type('qwer');

		cy.get('.btn-login').click();
		cy.get('.page-card-head').contains('Invalid Login. Try again.');
		cy.location('pathname').should('eq', '/login');
	});
});
