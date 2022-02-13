context('Grid', () => {
	beforeEach(() => {
		cy.login();
		cy.visit('/app/website');
	});
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_contact_phone_nos_records");
		});
	});
	it('update docfield property using update_docfield_property', () => {
		cy.visit('/app/contact/Test Contact');
		cy.window().its("cur_frm").then(frm => {
			cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
			let field = frm.get_field("phone_nos");
			field.grid.update_docfield_property("is_primary_phone", "hidden", true);

			cy.get('@table').find('[data-idx="1"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="is_primary_phone"]').should("be.hidden");
			cy.get('@table-form').find('.grid-footer-toolbar').click();

			cy.get('@table').find('[data-idx="2"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="is_primary_phone"]').should("be.hidden");
			cy.get('@table-form').find('.grid-footer-toolbar').click();
		});
	});
	it('update docfield property using toggle_display', () => {
		cy.visit('/app/contact/Test Contact');
		cy.window().its("cur_frm").then(frm => {
			cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
			let field = frm.get_field("phone_nos");
			field.grid.toggle_display("is_primary_mobile_no", false);

			cy.get('@table').find('[data-idx="1"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="is_primary_mobile_no"]').should("be.hidden");
			cy.get('@table-form').find('.grid-footer-toolbar').click();

			cy.get('@table').find('[data-idx="2"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="is_primary_mobile_no"]').should("be.hidden");
			cy.get('@table-form').find('.grid-footer-toolbar').click();
		});
	});
	it('update docfield property using toggle_enable', () => {
		cy.visit('/app/contact/Test Contact');
		cy.window().its("cur_frm").then(frm => {
			cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
			let field = frm.get_field("phone_nos");
			field.grid.toggle_enable("phone", false);


			cy.get('@table').find('[data-idx="1"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="phone"] .control-value').should('have.class', 'like-disabled-input');
			cy.get('@table-form').find('.grid-footer-toolbar').click();

			cy.get('@table').find('[data-idx="2"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get('@table-form').find('.frappe-control[data-fieldname="phone"] .control-value').should('have.class', 'like-disabled-input');
			cy.get('@table-form').find('.grid-footer-toolbar').click();
		});
	});
	it('update docfield property using toggle_reqd', () => {
		cy.visit('/app/contact/Test Contact');
		cy.window().its("cur_frm").then(frm => {
			cy.get('.frappe-control[data-fieldname="phone_nos"]').as('table');
			let field = frm.get_field("phone_nos");
			field.grid.toggle_reqd("phone", false);

			cy.get('@table').find('[data-idx="1"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get_field("phone").as('phone-field');
			cy.get('@phone-field').focus().clear().wait(500).blur();
			cy.get('@phone-field').should("not.have.class", "has-error");
			cy.get('@table-form').find('.grid-footer-toolbar').click();

			cy.get('@table').find('[data-idx="2"] .edit-grid-row').click();
			cy.get('.grid-row-open').as('table-form');
			cy.get_field("phone").as('phone-field');
			cy.get('@phone-field').focus().clear().wait(500).blur();
			cy.get('@phone-field').should("not.have.class", "has-error");
			cy.get('@table-form').find('.grid-footer-toolbar').click();

		});
	});
});

