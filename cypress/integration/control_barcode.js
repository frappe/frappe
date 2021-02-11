context('Control Barcode', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/app/website');
	});

	function get_dialog_with_barcode() {
		return cy.dialog({
			title: 'Barcode',
			fields: [
				{
					label: 'Barcode',
					fieldname: 'barcode',
					fieldtype: 'Barcode'
				}
			]
		});
	}

	it('should generate barcode on setting a value', () => {
		get_dialog_with_barcode().as('dialog');

		cy.get('.frappe-control[data-fieldname=barcode] input')
			.focus()
			.type('123456789')
			.blur();
		cy.get('.frappe-control[data-fieldname=barcode] svg[data-barcode-value="123456789"]')
			.should('exist');

		cy.get('@dialog').then(dialog => {
			let value = dialog.get_value('barcode');
			expect(value).to.contain('<svg');
			expect(value).to.contain('data-barcode-value="123456789"');
		});
	});

	it('should reset when input is cleared', () => {
		get_dialog_with_barcode().as('dialog');

		cy.get('.frappe-control[data-fieldname=barcode] input')
			.focus()
			.type('123456789')
			.blur();
		cy.get('.frappe-control[data-fieldname=barcode] input')
			.clear()
			.blur();
		cy.get('.frappe-control[data-fieldname=barcode] svg[data-barcode-value="123456789"]')
			.should('not.exist');

		cy.get('@dialog').then(dialog => {
			let value = dialog.get_value('barcode');
			expect(value).to.equal('');
		});
	});
});
