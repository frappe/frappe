context('Rating Control', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
	});

	it('click on the star rating to record value', () => {
		cy.visit('/desk')
		cy.dialog('Rating', {
			'fieldname': 'rate',
			'fieldtype': 'Rating',
		}).as('dialog');

		cy.get('div.rating')
			.children('i.fa')
			.first()
			.click()
			.should('have.class', 'star-click');
		cy.get('@dialog').then(dialog => {
			var value = dialog.get_value('rate');
			expect(value).to.equal(1);
		})
	});

	it('hover on the star', () => {
		cy.visit('/desk')
		cy.dialog('Rating', {
			'fieldname': 'rate',
			'fieldtype': 'Rating',
		})
		cy.get('div.rating')
			.children('i.fa')
			.first()
			.invoke('trigger', 'mouseenter')
			.should('have.class', 'star-hover')
			.invoke('trigger', 'mouseleave')
			.should('not.have.class', 'star-hover');
	});
});