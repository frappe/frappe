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
