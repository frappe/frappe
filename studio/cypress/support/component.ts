import "./commands"
// App styles so dropped components render the same way they do in the editor
import "@/index.css"

import { createPinia, setActivePinia } from "pinia"
import { mount } from "cypress/vue"

// Activate Pinia before any spec imports run. Some modules (e.g. useCanvasDropZone)
// call useCanvasStore() at module top-level, so a Pinia must be active the moment
// StudioCanvas is imported — in the real app this is guaranteed by app.use(pinia)
// running before the lazily-loaded canvas. Reuse this instance in cy.mount.
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
