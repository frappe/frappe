import 'cypress-file-upload';
import '@testing-library/cypress/add-commands';
import '@4tw/cypress-drag-drop';
// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... });
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... });
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... });
//
//
// -- This is will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... });
Cypress.Commands.add('login', (email, password) => {
	if (!email) {
		email = 'Administrator';
	}
	if (!password) {
		password = Cypress.config('adminPassword');
	}
	cy.request({
		url: '/api/method/login',
		method: 'POST',
		body: {
			usr: email,
			pwd: password
		}
	});
});

Cypress.Commands.add('call', (method, args) => {
	return cy
		.window()
		.its('frappe.csrf_token')
		.then(csrf_token => {
			return cy
				.request({
					url: `/api/method/${method}`,
					method: 'POST',
					body: args,
					headers: {
						Accept: 'application/json',
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': csrf_token
					}
				})
				.then(res => {
					expect(res.status).eq(200);
					return res.body;
				});
		});
});

Cypress.Commands.add('get_list', (doctype, fields = [], filters = []) => {
	filters = JSON.stringify(filters);
	fields = JSON.stringify(fields);
	let url = `/api/resource/${doctype}?fields=${fields}&filters=${filters}`;
	return cy
		.window()
		.its('frappe.csrf_token')
		.then(csrf_token => {
			return cy
				.request({
					method: 'GET',
					url,
					headers: {
						Accept: 'application/json',
						'X-Frappe-CSRF-Token': csrf_token
					}
				})
				.then(res => {
					expect(res.status).eq(200);
					return res.body;
				});
		});
});

Cypress.Commands.add('get_doc', (doctype, name) => {
	return cy
		.window()
		.its('frappe.csrf_token')
		.then(csrf_token => {
			return cy
				.request({
					method: 'GET',
					url: `/api/resource/${doctype}/${name}`,
					headers: {
						Accept: 'application/json',
						'X-Frappe-CSRF-Token': csrf_token
					}
				})
				.then(res => {
					expect(res.status).eq(200);
					return res.body;
				});
		});
});

Cypress.Commands.add('remove_doc', (doctype, name) => {
	return cy
		.window()
		.its('frappe.csrf_token')
		.then(csrf_token => {
			return cy
				.request({
					method: 'DELETE',
					url: `/api/resource/${doctype}/${name}`,
					headers: {
						Accept: 'application/json',
						'X-Frappe-CSRF-Token': csrf_token
					}
				})
				.then(res => {
					expect(res.status).eq(202);
					return res.body;
				});
		});
});

Cypress.Commands.add('create_records', doc => {
	return cy
		.call('frappe.tests.ui_test_helpers.create_if_not_exists', {doc})
		.then(r => r.message);
});

Cypress.Commands.add('set_value', (doctype, name, obj) => {
	return cy.call('frappe.client.set_value', {
		doctype,
		name,
		fieldname: obj
	});
});

Cypress.Commands.add('fill_field', (fieldname, value, fieldtype = 'Data') => {
	cy.get_field(fieldname, fieldtype).as('input');

	if (['Date', 'Time', 'Datetime'].includes(fieldtype)) {
		cy.get('@input').click().wait(200);
		cy.get('.datepickers-container .datepicker.active').should('exist');
	}
	if (fieldtype === 'Time') {
		cy.get('@input').clear().wait(200);
	}

	if (fieldtype === 'Select') {
		cy.get('@input').select(value);
	} else {
		cy.get('@input').type(value, {waitForAnimations: false, force: true, delay: 100});
	}
	return cy.get('@input');
});

Cypress.Commands.add('get_field', (fieldname, fieldtype = 'Data') => {
	let field_element = fieldtype === 'Select' ? 'select': 'input';
	let selector = `[data-fieldname="${fieldname}"] ${field_element}:visible`;

	if (fieldtype === 'Text Editor') {
		selector = `[data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]:visible`;
	}
	if (fieldtype === 'Code') {
		selector = `[data-fieldname="${fieldname}"] .ace_text-input`;
	}

	return cy.get(selector).first();
});

Cypress.Commands.add('fill_table_field', (tablefieldname, row_idx, fieldname, value, fieldtype = 'Data') => {
	cy.get_table_field(tablefieldname, row_idx, fieldname, fieldtype).as('input');

	if (['Date', 'Time', 'Datetime'].includes(fieldtype)) {
		cy.get('@input').click().wait(200);
		cy.get('.datepickers-container .datepicker.active').should('exist');
	}
	if (fieldtype === 'Time') {
		cy.get('@input').clear().wait(200);
	}

	if (fieldtype === 'Select') {
		cy.get('@input').select(value);
	} else {
		cy.get('@input').type(value, {waitForAnimations: false, force: true});
	}
	return cy.get('@input');
});

Cypress.Commands.add('get_table_field', (tablefieldname, row_idx, fieldname, fieldtype = 'Data') => {
	let selector = `.frappe-control[data-fieldname="${tablefieldname}"]`;
	selector += ` [data-idx="${row_idx}"]`;
	selector += ` .form-in-grid`;

	if (fieldtype === 'Text Editor') {
		selector += ` [data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]`;
	} else if (fieldtype === 'Code') {
		selector += ` [data-fieldname="${fieldname}"] .ace_text-input`;
	} else {
		selector += ` .form-control[data-fieldname="${fieldname}"]`;
	}

	return cy.get(selector);
});

Cypress.Commands.add('awesomebar', text => {
	cy.get('#navbar-search').type(`${text}{downarrow}{enter}`, {delay: 700});
});

Cypress.Commands.add('new_form', doctype => {
	let dt_in_route = doctype.toLowerCase().replace(/ /g, '-');
	cy.visit(`/app/${dt_in_route}/new`);
	cy.get('body').should('have.attr', 'data-route', `Form/${doctype}/new-${dt_in_route}-1`);
	cy.get('body').should('have.attr', 'data-ajax-state', 'complete');
});

Cypress.Commands.add('go_to_list', doctype => {
	let dt_in_route = doctype.toLowerCase().replace(/ /g, '-');
	cy.visit(`/app/${dt_in_route}`);
});

Cypress.Commands.add('clear_cache', () => {
	cy.window()
		.its('frappe')
		.then(frappe => {
			frappe.ui.toolbar.clear_cache();
		});
});

Cypress.Commands.add('dialog', opts => {
	return cy.window().then(win => {
		var d = new win.frappe.ui.Dialog(opts);
		d.show();
		return d;
	});
});

Cypress.Commands.add('get_open_dialog', () => {
	return cy.get('.modal:visible').last();
});

Cypress.Commands.add('hide_dialog', () => {
	cy.wait(300);
	cy.get_open_dialog().find('.btn-modal-close').click();
	cy.get('.modal:visible').should('not.exist');
});

Cypress.Commands.add('insert_doc', (doctype, args, ignore_duplicate) => {
	return cy
		.window()
		.its('frappe.csrf_token')
		.then(csrf_token => {
			return cy
				.request({
					method: 'POST',
					url: `/api/resource/${doctype}`,
					body: args,
					headers: {
						Accept: 'application/json',
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': csrf_token
					},
					failOnStatusCode: !ignore_duplicate
				})
				.then(res => {
					let status_codes = [200];
					if (ignore_duplicate) {
						status_codes.push(409);
					}
					expect(res.status).to.be.oneOf(status_codes);
					return res.body.data;
				});
		});
});

Cypress.Commands.add('add_filter', () => {
	cy.get('.filter-section .filter-button').click();
	cy.wait(300);
	cy.get('.filter-popover').should('exist');
});

Cypress.Commands.add('clear_filters', () => {
	let has_filter = false;
	cy.intercept({
		method: 'POST',
		url: 'api/method/frappe.model.utils.user_settings.save'
	}).as('filter-saved');
	cy.get('.filter-section .filter-button').click({force: true});
	cy.wait(300);
	cy.get('.filter-popover').should('exist');
	cy.get('.filter-popover').then(popover => {
		if (popover.find('input.input-with-feedback')[0].value != '') {
			has_filter = true;
		}
	});
	cy.get('.filter-popover').find('.clear-filters').click();
	cy.get('.filter-section .filter-button').click();
	cy.window().its('cur_list').then(cur_list => {
		cur_list && cur_list.filter_area && cur_list.filter_area.clear();
		has_filter && cy.wait('@filter-saved');
	});
});

Cypress.Commands.add('click_modal_primary_button', (btn_name) => {
	cy.get('.modal-footer > .standard-actions > .btn-primary').contains(btn_name).trigger('click', {force: true});
});

Cypress.Commands.add('click_sidebar_button', (btn_name) => {
	cy.get('.list-group-by-fields .list-link > a').contains(btn_name).click({force: true});
});

Cypress.Commands.add('click_listview_row_item', (row_no) => {
	cy.get('.list-row > .level-left > .list-subject > .level-item > .ellipsis').eq(row_no).click({force: true});
});

Cypress.Commands.add('click_listview_row_item_with_text', (text) => {
	cy.get('.list-row > .level-left > .list-subject > .level-item > .ellipsis')
		.contains(text)
		.first()
		.click({force: true});
});

Cypress.Commands.add('click_filter_button', () => {
	cy.get('.filter-selector > .btn').click();
});

Cypress.Commands.add('click_listview_primary_button', (btn_name) => {
	cy.get('.primary-action').contains(btn_name).click({force: true});
});

Cypress.Commands.add('click_timeline_action_btn', (btn_name) => {
	cy.get('.timeline-message-box .actions .action-btn').contains(btn_name).click();
});

Cypress.Commands.add('select_listview_row_checkbox', (row_no) => {
	cy.get('.frappe-list .select-like > .list-row-checkbox').eq(row_no).click();
});
