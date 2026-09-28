import { pinia } from "../support/component"

import { defineComponent, h } from "vue"
import { setActivePinia } from "pinia"
import { useKeyboardShortcut, type KeyboardShortcutConfig } from "frappe-ui"

import StudioCommandPalette from "@/components/CommandPalette/StudioCommandPalette.vue"
import { commandShortcuts } from "@/components/Commands"
import useStudioStore from "@/stores/studioStore"

const mod = Cypress.platform === "darwin" ? { metaKey: true } : { ctrlKey: true }

const Harness = defineComponent({
	setup() {
		// Studio types combo as a plain string: its frappe-ui import is untyped (src/lib.d.ts)
		useKeyboardShortcut(commandShortcuts() as KeyboardShortcutConfig[])
		return () => h(StudioCommandPalette)
	},
})

function press(key: string, code: string, modifiers: Partial<KeyboardEventInit> = {}) {
	cy.document().trigger("keydown", { eventConstructor: "KeyboardEvent", key, code, ...modifiers })
}

describe("command palette and shortcuts", () => {
	let store: ReturnType<typeof useStudioStore>

	beforeEach(() => {
		setActivePinia(pinia)
		store = useStudioStore()
		store.studioLayout.showLeftPanel = true
		store.studioLayout.showRightPanel = true
		cy.mount(Harness, { global: { plugins: [pinia] } })
	})

	it("opens with Mod+K and runs the chosen command", () => {
		press("k", "KeyK", mod)
		cy.get("input[placeholder='Search commands...']").should("be.focused").type("left panel{enter}")
		cy.get("input[placeholder='Search commands...']").should("not.exist")
		cy.wrap(null).should(() => expect(store.studioLayout.showLeftPanel).to.be.false)
	})

	it("finds a command by its name in the shortcuts dialog", () => {
		press("k", "KeyK", mod)
		cy.get("input[placeholder='Search commands...']").type("toggle panels")
		cy.contains("Hide Panels").should("be.visible")
	})

	// Go to Page is the stepped command here; any step should behave the same
	it("keeps focus in the search when a step opens; Escape clears, backs out, then closes", () => {
		press("k", "KeyK", mod)
		cy.contains("Go to Page").click()
		cy.get("input[placeholder='Search by title or route...']").should("be.focused").type("home{esc}")
		cy.get("input[placeholder='Search by title or route...']").should("have.value", "").type("{esc}")
		cy.get("input[placeholder='Search commands...']").should("be.focused").type("{esc}")
		cy.get("input[placeholder='Search commands...']").should("not.exist")
	})

	it("runs a command's key binding", () => {
		press("\\", "Backslash", mod)
		cy.wrap(null).should(() => {
			expect(store.studioLayout.showLeftPanel).to.be.false
			expect(store.studioLayout.showRightPanel).to.be.false
		})
	})
})
