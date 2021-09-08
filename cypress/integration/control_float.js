context('Control Float', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		cy.window().its('frappe').then(frappe => {
			frappe.boot.sysdefaults.number_format = '#.###,##';
		});
	});

	function get_dialog_with_float() {
		return cy.dialog({
			title: 'Float Check',
			fields: [{
				'fieldname': 'float_number',
				'fieldtype': 'Float',
				'Label': 'Float',
			}]
		});
	}

	it('check value changes', () => {
		get_dialog_with_float().as('dialog');
		cy.get_field('float_number', 'Float').clear()
		cy.fill_field('float_number', '36487,334', 'Float').blur();
		cy.get_field('float_number', 'Float').should('have.value', '36.487,334');

	});
});
