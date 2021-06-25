context('API Resources', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/website');
	});

	it('Creates two Comments', () => {
		cy.insert_doc('Comment', { comment_type: 'Comment', content: "hello" });
		cy.insert_doc('Comment', { comment_type: 'Comment', content: "world" });
	});

	it('Lists the Comments', () => {
		cy.get_list('Comment')
			.its('data')
			.then(data => expect(data.length).to.be.at.least(2));

		cy.get_list('Comment', ['name', 'content'], [['content', '=', 'hello']])
			.then(body => {
				expect(body).to.have.property('data');
				expect(body.data).to.have.lengthOf(1);
				expect(body.data[0]).to.have.property('content');
				expect(body.data[0]).to.have.property('name');
			});
	});

	it('Gets each Comment', () => {
		cy.get_list('Comment').then(body => body.data.forEach(comment => {
			cy.get_doc('Comment', comment.name);
		}));
	});

	it('Removes the Comments', () => {
		cy.get_list('Comment').then(body => body.data.forEach(comment => {
			cy.remove_doc('Comment', comment.name);
		}));
	});
});
