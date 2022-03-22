context('Notification', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		cy.create_records([
			{
				doctype: 'Notification Log',
				document_type: "ToDo",
				for_user: "Administrator",
				from_user: "Administrator",
				subject: "<strong>Administrator</strong> mentioned you in a comment in <strong>ToDo</strong> <b class=\"subject-title\"><div class=\"ql-editor read-mode\"><p>New Todo</p></div></b>",
				type: "Mention",
				email_content: "Test 1"
			},
			{
				doctype: 'Notification Log',
				document_type: "ToDo",
				for_user: "Administrator",
				from_user: "Administrator",
				subject: "<strong>Administrator</strong> mentioned you in a comment in <strong>ToDo</strong> <b class=\"subject-title\"><div class=\"ql-editor read-mode\"><p>New Todo</p></div></b>",
				type: "Mention",
				email_content: "Test 2"
			}
		]);
	});

	it('Check Mark as Read & Mark as Unread', () => {
		cy.visit('/app/website');
		cy.get('.nav-item.dropdown-notifications .notifications-icon').click();
		cy.get('.notifications-list .notification-list-body').as('notifications-list');

		cy.get('@notifications-list').find('.notification-item.unread')
			.first()
			.realHover()
			.find('.mark-as-read')
			.click();
		cy.get('@notifications-list').find('.notification-item').first().should('have.class', 'read');

		cy.get('@notifications-list').find('.notification-item.read')
			.first()
			.realHover()
			.find('.mark-as-unread')
			.click();
		cy.get('@notifications-list').find('.notification-item').first().should('have.class', 'unread');
	});
});