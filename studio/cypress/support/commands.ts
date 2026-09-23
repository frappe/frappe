/// <reference types="cypress" />
// Server commands ported from frappe/cypress/support/commands.js. They skip the CSRF header:
// sessions created through /api/method/login have no CSRF token to check.

declare global {
	namespace Cypress {
		interface Chainable {
			login(email?: string, password?: string): Chainable<void>
			call(method: string, args?: object): Chainable<any>
			get_doc(doctype: string, name: string): Chainable<any>
			insert_doc(doctype: string, args: object, ignore_duplicate?: boolean): Chainable<any>
			update_doc(doctype: string, docname: string, args: object): Chainable<any>
			remove_doc(doctype: string, name: string, ignore_missing?: boolean): Chainable<any>
		}
	}
}

// The dev server proxies /api to the bench; this header picks the test site there
const siteHeader = () => ({ "X-Frappe-Site-Name": Cypress.expose("site") })

// supports the options-object form, which every command here uses
Cypress.Commands.overwrite("request", (originalFn, options: any) => {
	return originalFn({ ...options, headers: { ...siteHeader(), ...options.headers } })
})

// Unlike frappe's, this logs in on every call: component specs can't use cy.session, and
// Cypress clears the session cookie between tests
Cypress.Commands.add("login", (email?: string, password?: string) => {
	return cy.env(["adminPassword"]).then(({ adminPassword }) => {
		cy.request({
			url: "/api/method/login",
			method: "POST",
			body: { usr: email || "Administrator", pwd: password || adminPassword },
		})
		// the app's own fetches go through the proxy too
		cy.intercept("/api/**", (request) => {
			Object.assign(request.headers, siteHeader())
		})
	})
})

Cypress.Commands.add("call", (method: string, args?: object) => {
	return cy.request({ url: `/api/method/${method}`, method: "POST", body: args }).then((response) => {
		expect(response.status).eq(200)
		return response.body
	})
})

Cypress.Commands.add("get_doc", (doctype: string, name: string) => {
	return cy.request({ url: `/api/resource/${doctype}/${name}`, method: "GET" }).then((response) => {
		expect(response.status).eq(200)
		return response.body
	})
})

Cypress.Commands.add("insert_doc", (doctype: string, args: object, ignore_duplicate?: boolean) => {
	return cy
		.request({
			url: `/api/resource/${doctype}`,
			method: "POST",
			body: { doctype, ...args },
			failOnStatusCode: !ignore_duplicate,
		})
		.then((response) => {
			expect(response.status).to.be.oneOf(ignore_duplicate ? [200, 409] : [200])
			return response.body.data
		})
})

Cypress.Commands.add("update_doc", (doctype: string, docname: string, args: object) => {
	return cy
		.request({ url: `/api/resource/${doctype}/${docname}`, method: "PUT", body: args })
		.then((response) => {
			expect(response.status).eq(200)
			return response.body.data
		})
})

Cypress.Commands.add("remove_doc", (doctype: string, name: string, ignore_missing?: boolean) => {
	return cy
		.request({ url: `/api/resource/${doctype}/${name}`, method: "DELETE", failOnStatusCode: !ignore_missing })
		.then((response) => response.body)
})

export {}
