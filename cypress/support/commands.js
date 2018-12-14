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
	cy.request({
		url: '/',
		method: 'POST',
		body: {
			cmd: 'login',
			usr: email,
			pwd: password
		}
	});
});

Cypress.Commands.add('fill_field', (fieldname, value, fieldtype='Data') => {
	let selector = `.form-control[data-fieldname="${fieldname}"]`;

	if (fieldtype === 'Text Editor') {
		selector = `[data-fieldname="${fieldname}"] .ql-editor`;
	}

	cy.get(selector).as('input');

	if (fieldtype === 'Select') {
		return cy.get('@input').select(value);
	} else {
		return cy.get('@input').type(value);
	}
});