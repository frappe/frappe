context('Discussions', () => {
	before(() => {
		cy.login();
		cy.visit('/app');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call('frappe.tests.ui_test_helpers.create_data_for_discussions');
		});
	});

	const reply_through_modal = () => {
		cy.visit('/test-page-discussions');

		// Open the modal
		cy.get('.reply').click();
		cy.wait(500);
		cy.get('.discussion-modal').should('be.visible');

		// Enter title
		cy.get('.modal .topic-title').type('Discussion from tests')
			.should('have.value', 'Discussion from tests');

		// Enter comment
		cy.get('.modal .comment-field')
			.type('This is a discussion from the cypress ui tests.')
			.should('have.value', 'This is a discussion from the cypress ui tests.');

		// Submit
		cy.get('.modal .submit-discussion').click();
		cy.wait(2000);

		// Check if discussion is added to page and content is visible
		cy.get('.sidebar-parent:first .discussion-topic-title').should('have.text', 'Discussion from tests');
		cy.get('.discussion-on-page:visible').should('have.class', 'show');
		cy.get('.discussion-on-page:visible .reply-card .reply-text')
			.should('have.text', 'This is a discussion from the cypress ui tests.\n');

	};

	const reply_through_comment_box = () => {
		cy.get('.discussion-on-page:visible .comment-field')
			.type('This is a discussion from the cypress ui tests. \n\nThis comment was entered through the commentbox on the page.')
			.should('have.value', 'This is a discussion from the cypress ui tests. \n\nThis comment was entered through the commentbox on the page.');

		cy.get('.discussion-on-page:visible .submit-discussion').click();
		cy.wait(3000);
		cy.get('.discussion-on-page:visible').should('have.class', 'show');
		cy.get('.discussion-on-page:visible').children(".reply-card").eq(1).children(".reply-text")
			.should('have.text', 'This is a discussion from the cypress ui tests. \n\nThis comment was entered through the commentbox on the page.\n');
	};

	const cancel_and_clear_comment_box = () => {
		cy.get('.discussion-on-page:visible .comment-field')
			.type('This is a discussion from the cypress ui tests.')
			.should('have.value', 'This is a discussion from the cypress ui tests.');

		cy.get('.discussion-on-page:visible .cancel-comment').click();
		cy.get('.discussion-on-page:visible .comment-field').should('have.value', '');
	};

	it('reply through modal', reply_through_modal);
	it('reply through comment box', reply_through_comment_box);
	it('cancel and clear comment box', cancel_and_clear_comment_box);
});
