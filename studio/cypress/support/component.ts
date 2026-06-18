import "./commands"
import "@/index.css"

import { createPinia, setActivePinia } from "pinia"
import { mount } from "cypress/vue"

export const pinia = createPinia()
setActivePinia(pinia)

declare global {
	namespace Cypress {
		interface Chainable {
			mount: typeof mount
		}
	}
}

Cypress.Commands.add("mount", mount)

// The studio app fires background resource fetches (pages, apps, studio components)
// that have no Frappe backend in the component-test environment. Those rejections
// are unrelated to what these tests assert, so don't let them fail the run.
Cypress.on("uncaught:exception", () => false)
