import "./commands"
import "@/index.css"

import { createPinia, setActivePinia } from "pinia"
import { mount } from "cypress/vue"

export const pinia = createPinia()
setActivePinia(pinia)

declare global {
	// declared in src/main.ts, which specs don't load
	interface Window {
		is_developer_mode?: boolean
	}

	namespace Cypress {
		interface Chainable {
			mount: typeof mount
		}
	}
}

Cypress.Commands.add("mount", mount)
