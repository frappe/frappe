context('Control Phone', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
	});

	function get_dialog_with_phone(s) {
		return cy.dialog({
			title: 'Phone',
			fields: [{
				'fieldname': 'phone',
				'fieldtype': 'Phone',
			}]
		});
	}

	it('should set flag and data', () => {
		get_dialog_with_phone().as('dialog');
		cy.get('.selected-phone').click();
		cy.get('.phone-picker .phone-wrapper[id="afghanistan"]').click();
		cy.get('.phone-picker .phone-wrapper[id="india"]').click();
		cy.get('.selected-phone .country').should('have.text', '+91')
		cy.get('.selected-phone > .icon > use').should('have.attr', 'href').and('include', '#in')

		let phone_number = '9312672712'
		cy.get('.selected-phone').click().first();
		cy.get('.frappe-control[data-fieldname=phone] input')
			.first()
			.click();
		cy.get('.frappe-control[data-fieldname=phone]')
			.findByRole('textbox')
			.first()
			.type(phone_number);

		cy.get('.frappe-control[data-fieldname=phone] input').first().should('have.value', phone_number);
		cy.get('.frappe-control[data-fieldname=phone] input').first().blur();
		cy.get('@dialog').then(dialog => {
			let value = dialog.fields_dict.phone.value;
			expect(value).to.equal('+91-' + phone_number);
		});
	});

	it('case insensitive search for country and clear search', () => {
		let search_text = 'india';
		cy.get('.selected-phone').click().first();
		cy.get('.phone-picker').findByRole('searchbox').click().type(search_text);
		cy.get('.phone-section .phone-wrapper:not(.hidden)').then(i => {
			cy.get(`.phone-section .phone-wrapper[id*='${search_text.toLowerCase()}']`).then(countries => {
				expect(i.length).to.equal(countries.length);
			});
		});

		cy.get('.phone-picker').findByRole('searchbox').clear().blur();
		cy.get('.phone-section .phone-wrapper').should('not.have.class', 'hidden');
	});

});
