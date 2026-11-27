import "./commands"
import "@/index.css"

import { createPinia, setActivePinia } from "pinia"
import { mount } from "cypress/vue"
import Block from "@/runtime/utils/block"
import { componentHasDefaultSlot } from "@/utils/componentSlots"
import useCanvasStore from "@/stores/canvasStore"

export const pinia = createPinia()
setActivePinia(pinia)

Block.setDefaultSlotLookup(componentHasDefaultSlot)
Block.setActiveCanvasLookup(() => useCanvasStore().activeCanvas)

declare global {
	// declared in src/main.ts and src/runtime/renderer.ts, which specs don't load
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
