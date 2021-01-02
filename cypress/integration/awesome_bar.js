context('Awesome Bar', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/website');
	});

	beforeEach(() => {
		cy.get('.navbar .navbar-home').click();
	});

	it('navigates to doctype list', () => {
		cy.get('#navbar-search').type('todo', { delay: 200 });
		cy.get('#navbar-search + ul').should('be.visible');
		cy.get('#navbar-search').type('{downarrow}{enter}', { delay: 100 });

		cy.get('.title-text').should('contain', 'To Do');

		cy.location('pathname').should('eq', '/app/todo');
	});

	it('find text in doctype list', () => {
		cy.get('#navbar-search')
			.type('test in todo{downarrow}{enter}', { delay: 200 });

		cy.get('.title-text').should('contain', 'To Do');

		cy.get('[data-original-title="Name"] > .input-with-feedback')
			.should('have.value', '%test%');
	});

	it('navigates to new form', () => {
		cy.get('#navbar-search')
			.type('new blog post{downarrow}{enter}', { delay: 200 });

		cy.get('.title-text:visible').should('have.text', 'New Blog Post');
	});

	it('calculates math expressions', () => {
		cy.get('#navbar-search')
			.type('55 + 32{downarrow}{enter}', { delay: 200 });

		cy.get('.modal-title').should('contain', 'Result');
		cy.get('.msgprint').should('contain', '55 + 32 = 87');
	});
});
