import "./commands"
import "@/index.css"

import { createPinia, setActivePinia } from "pinia"
import { mount } from "cypress/vue"

export const pinia = createPinia()
setActivePinia(pinia)

declare global {
	// declared in src/main.ts and src/renderer.ts, which specs don't load
	interface Window {
		is_developer_mode?: boolean
		app_name?: string
	}

	namespace Cypress {
		interface Chainable {
			mount: typeof mount
		}
	}
}

Cypress.Commands.add("mount", mount)

// The data modules fetch their resources on import, before a spec can log in, and a component
// can leave a request behind when its test ends. Nothing awaits these requests. When one fails,
// its rejection is not an error of the test that runs at that moment.
Cypress.on(
	"uncaught:exception",
	(error, _runnable, promise) =>
		!(promise && /frappe-ui\/src\/(utils\/request|resources)/.test(error.stack || "")),
)
