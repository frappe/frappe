context('Control Icon', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	function get_dialog_with_icon() {
		return cy.dialog({
			title: 'Icon',
			fields: [{
				label: 'Icon',
				fieldname: 'icon',
				fieldtype: 'Icon'
			}]
		});
	}

	it('should set icon', () => {
		get_dialog_with_icon().as('dialog');
		cy.get('.frappe-control[data-fieldname=icon] input').first().click();

		cy.get('.icon-picker .icon-wrapper[id=active]').first().click();
		cy.get('.frappe-control[data-fieldname=icon] input').first().should('have.value', 'active');
		cy.get('@dialog').then(dialog => {
			let value = dialog.get_value('icon');
			expect(value).to.equal('active');
		});

		cy.get('.icon-picker .icon-wrapper[id=resting]').first().click();
		cy.get('.frappe-control[data-fieldname=icon] input').first().should('have.value', 'resting');
		cy.get('@dialog').then(dialog => {
			let value = dialog.get_value('icon');
			expect(value).to.equal('resting');
		});
	});

	it('search for icon and clear search input', () => {
		let search_text = 'ed';
		cy.get('.icon-picker input[type=search]').first().click().type(search_text);
		cy.get('.icon-section .icon-wrapper:not(.hidden)').then(i => {
			cy.get(`.icon-section .icon-wrapper[id*='${search_text}']`).then(icons => {
				expect(i.length).to.equal(icons.length);
			});
		});

		cy.get('.icon-picker input[type=search]').clear().blur();
		cy.get('.icon-section .icon-wrapper').should('not.have.class', 'hidden');
	});

});