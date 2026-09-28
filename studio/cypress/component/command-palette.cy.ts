import { pinia } from "../support/component"

import { defineComponent, h } from "vue"
import { setActivePinia } from "pinia"
// @ts-ignore
import { KeyboardShortcutsDialog, useKeyboardShortcut } from "frappe-ui"

import StudioCommandPalette from "@/components/CommandPalette/StudioCommandPalette.vue"
import { commandShortcuts } from "@/components/Commands"
import useStudioStore from "@/stores/studioStore"

const mod = Cypress.platform === "darwin" ? { metaKey: true } : { ctrlKey: true }

const Harness = defineComponent({
	setup() {
		const store = useStudioStore()
		useKeyboardShortcut(commandShortcuts())
		return () => [
			h(StudioCommandPalette),
			h(KeyboardShortcutsDialog, {
				open: store.showShortcutsDialog,
				"onUpdate:open": (open: boolean) => (store.showShortcutsDialog = open),
			}),
		]
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
		store.showShortcutsDialog = false
		cy.mount(Harness, { global: { plugins: [pinia] } })
	})

	it("opens with Mod+K and runs the chosen command", () => {
		press("k", "KeyK", mod)
		cy.get("input[placeholder='Search commands...']").should("be.focused").type("left panel{enter}")
		cy.get("input[placeholder='Search commands...']").should("not.exist")
		cy.wrap(null).should(() => expect(store.studioLayout.showLeftPanel).to.be.false)
	})

	it("steps into Go to Page and backs out with Escape", () => {
		press("k", "KeyK", mod)
		cy.contains("Go to Page").click()
		cy.get("input[placeholder='Search by title or route...']").should("be.focused").type("{esc}")
		cy.get("input[placeholder='Search commands...']").should("exist")
	})

	it("lists the Navigate commands in order", () => {
		store.activeApp = { name: "test-app" } as any
		store.activePage = { name: "test-page" } as any
		press("k", "KeyK", mod)
		cy.contains("Navigate")
			.parent()
			.find("span.truncate, span.text-ellipsis")
			.then((titles) => {
				expect([...titles].map((title) => title.textContent?.trim())).to.deep.equal([
					"Go to Dashboard",
					"View App in Desk",
					"View Page in Desk",
					"Go to Page",
				])
			})
	})

	it("runs a command's key binding", () => {
		press("\\", "Backslash", mod)
		cy.wrap(null).should(() => {
			expect(store.studioLayout.showLeftPanel).to.be.false
			expect(store.studioLayout.showRightPanel).to.be.false
		})
	})

	it("lists registered shortcuts in the shortcuts dialog", () => {
		press("?", "Slash", { shiftKey: true })
		cy.contains("Open Command Palette").should("be.visible")
		cy.contains("Toggle Left Panel").should("be.visible")
	})
})
