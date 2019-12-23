import 'cypress-file-upload';
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
	return cy.window().its('frappe.csrf_token').then(csrf_token => {
		return cy.request({
			url: `/api/method/${method}`,
			method: 'POST',
			body: args,
			headers: {
				'Accept': 'application/json',
				'Content-Type': 'application/json',
				'X-Frappe-CSRF-Token': csrf_token
			}
		}).then(res => {
			expect(res.status).eq(200);
			return res.body;
		});
	});
});

Cypress.Commands.add('get_list', (doctype, fields=[], filters=[]) => {
	return cy.window().its('frappe.csrf_token').then(csrf_token => {
		return cy.request({
			method: 'GET',
			url: `/api/resource/${doctype}?fields=${JSON.stringify(fields)}&filters=${JSON.stringify(filters)}`,
			headers: {
				'Accept': 'application/json',
				'X-Frappe-CSRF-Token': csrf_token
			}
		}).then(res => {
			expect(res.status).eq(200);
			return res.body;
		});
	});
});

Cypress.Commands.add('get_doc', (doctype, name) => {
	return cy.window().its('frappe.csrf_token').then(csrf_token => {
		return cy.request({
			method: 'GET',
			url: `/api/resource/${doctype}/${name}`,
			headers: {
				'Accept': 'application/json',
				'X-Frappe-CSRF-Token': csrf_token
			}
		}).then(res => {
			expect(res.status).eq(200);
			return res.body;
		});
	});
});

Cypress.Commands.add('create_doc', (doctype, args) => {
	return cy.window().its('frappe.csrf_token').then(csrf_token => {
		return cy.request({
			method: 'POST',
			url: `/api/resource/${doctype}`,
			body: args,
			headers: {
				'Accept': 'application/json',
				'Content-Type': 'application/json',
				'X-Frappe-CSRF-Token': csrf_token
			}
		}).then(res => {
			expect(res.status).eq(200);
			return res.body;
		});
	});
});

Cypress.Commands.add('remove_doc', (doctype, name) => {
	return cy.window().its('frappe.csrf_token').then(csrf_token => {
		return cy.request({
			method: 'DELETE',
			url: `/api/resource/${doctype}/${name}`,
			headers: {
				'Accept': 'application/json',
				'X-Frappe-CSRF-Token': csrf_token
			}
		}).then(res => {
			expect(res.status).eq(202);
			return res.body;
		});
	});
});

Cypress.Commands.add('create_records', (doc) => {
	return cy.call('frappe.tests.ui_test_helpers.create_if_not_exists', { doc })
		.then(r => r.message);
});

Cypress.Commands.add('fill_field', (fieldname, value, fieldtype='Data') => {
	let selector = `.form-control[data-fieldname="${fieldname}"]`;

	if (fieldtype === 'Text Editor') {
		selector = `[data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]`;
	}
	if (fieldtype === 'Code') {
		selector = `[data-fieldname="${fieldname}"] .ace_text-input`;
	}

	cy.get(selector).as('input');

	if (fieldtype === 'Select') {
		return cy.get('@input').select(value);
	} else {
		return cy.get('@input').type(value, {waitForAnimations: false});
	}
});

Cypress.Commands.add('awesomebar', (text) => {
	cy.get('#navbar-search').type(`${text}{downarrow}{enter}`, { delay: 100 });
});

Cypress.Commands.add('new_form', (doctype) => {
	cy.visit(`/desk#Form/${doctype}/New ${doctype} 1`);
});

Cypress.Commands.add('go_to_list', (doctype) => {
	cy.visit(`/desk#List/${doctype}/List`);
});

Cypress.Commands.add('clear_cache', () => {
	cy.window().its('frappe').then(frappe => {
		frappe.ui.toolbar.clear_cache();
	});
});

Cypress.Commands.add('dialog', (opts) => {
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