context('Awesome Bar', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});

	beforeEach(() => {
		cy.get('.navbar-home').click();
	});

	it('navigates to modules', () => {
		cy.get('#navbar-search')
			.type('modules{downarrow}{enter}', { delay: 100 });

		cy.location('hash').should('eq', '#modules');
	});

	it('navigates to doctype list', () => {
		cy.get('#navbar-search')
			.type('todo{downarrow}{enter}', { delay: 100 });

		cy.get('h1').should('contain', 'To Do');

		cy.location('hash').should('eq', '#List/ToDo/List');
	});

	it('find text in doctype list', () => {
		cy.get('#navbar-search')
			.type('test in todo{downarrow}{enter}', { delay: 100 });

		cy.get('h1').should('contain', 'To Do');

		cy.get('.toggle-filter')
			.should('have.length', 1)
			.should('contain', 'ID like %test%');
	});

	it('navigates to new form', () => {
		cy.get('#navbar-search')
			.type('new blog post{downarrow}{enter}', { delay: 100 });

		cy.get('.title-text:visible').should('have.text', 'New Blog Post 1');
	});

	it('calculates math expressions', () => {
		cy.get('#navbar-search')
			.type('55 + 32{downarrow}{enter}', { delay: 100 });

		cy.get('.modal-title').should('contain', 'Result');
		cy.get('.msgprint').should('contain', '55 + 32 = 87');
	});
});
