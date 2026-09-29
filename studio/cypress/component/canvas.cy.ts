import { pinia } from "../support/component"

import { defineComponent, h } from "vue"
import { setActivePinia } from "pinia"
// @ts-ignore
import { FrappeUIProvider, resourcesPlugin } from "frappe-ui"

import StudioCanvas from "@/components/StudioCanvas.vue"
import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { registerGlobalComponents } from "@/globals"
import router from "@/router/studio_router"
import session from "@/utils/session"
import useCanvasStore from "@/stores/canvasStore"
import { useStudioEvents } from "@/utils/useStudioEvents"

const canvasElement = () => document.querySelector(".canvas") as HTMLElement

describe("canvas navigation guard", () => {
	beforeEach(() => {
		// satisfy the router's login guard without a site
		session.initialized = true
		session.user.email = "test@example.com"
		session.hasPermission = true
		if (!router.hasRoute("TestPage")) {
			router.addRoute({ path: "/app/test/page", name: "TestPage", component: { render: () => h("div") } })
		}
		cy.wrap(router.push("/app/test/page"))

		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
		cy.mount(StudioCanvas as any, {
			props: { componentTree: getBlockInstance({ ...getBlockTemplate("body") }) },
			global: { plugins: [pinia, router, resourcesPlugin, { install: registerGlobalComponents }] },
		})
		cy.get(".canvas").should("exist")
	})

	it("cancels navigation triggered by a click inside the canvas", () => {
		cy.then(() => {
			canvasElement().dispatchEvent(new MouseEvent("mousedown", { bubbles: true }))
			canvasElement().dispatchEvent(new MouseEvent("mouseup", { bubbles: true }))
			return router.push({ name: "Home" })
		})
		cy.wrap(null).should(() => expect(router.currentRoute.value.name).to.eq("TestPage"))
	})

	it("allows navigation after a press in the canvas is released outside it", () => {
		cy.then(() => {
			canvasElement().dispatchEvent(new MouseEvent("mousedown", { bubbles: true, button: 2 }))
			document.body.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, button: 2 }))
		})
		cy.wait(10)
		cy.then(() => router.push({ name: "Home" }))
		cy.wrap(null).should(() => expect(router.currentRoute.value.name).to.eq("Home"))
	})
})

/**
 * A real keypress runs pending Vue work between the document's listeners and window's; a
 * dispatchEvent call runs them all at once. Replay it in those two halves.
 */
async function pressEscapeLikeABrowser() {
	document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))
	for (let i = 0; i < 20; i++) await Promise.resolve()
	window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))
}

describe("Escape in a fragment", () => {
	let canvasStore: ReturnType<typeof useCanvasStore>

	const pressEscape = (target: EventTarget = document.body) =>
		cy.then(() => target.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })))

	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
		canvasStore = useCanvasStore()
		cy.mount(
			defineComponent({
				setup() {
					useStudioEvents(() => {})
					// the provider hosts dialog.confirm, which asks before discarding unsaved changes
					return () => h(FrappeUIProvider, () => h("div", { role: "menu", tabindex: -1, id: "menu" }))
				},
			}),
			{ global: { plugins: [pinia] } },
		)
		cy.then(() => {
			canvasStore.resetFragments()
			canvasStore.editOnCanvas(getBlockInstance(getBlockTemplate("body")), () => {}, "Save", "Card")
			expect(canvasStore.editingMode).to.equal("fragment")
		})
	})

	it("leaves one nested fragment per press", () => {
		// a dialog opened from inside another dialog's content is a second fragment on the stack
		cy.then(() => canvasStore.editOnCanvas(getBlockInstance(getBlockTemplate("body")), () => {}, "Save", "Inner"))
		pressEscape()
		cy.wrap(null).should(() => {
			expect(canvasStore.fragmentStack.map((fragment) => fragment.fragmentName)).to.deep.equal(["Card"])
			expect(canvasStore.editingMode).to.equal("fragment")
		})
		pressEscape()
		cy.wrap(null).should(() => expect(canvasStore.editingMode).to.equal("page"))
	})

	it("keeps the discard confirmation open for a fragment with unsaved changes", () => {
		cy.then(() => (canvasStore.fragmentStack[0].dirty = true))
		cy.then(pressEscapeLikeABrowser)
		cy.contains("Discard unsaved changes in Card?").should("be.visible")
		cy.wait(50)
		cy.contains("Discard unsaved changes in Card?").should("be.visible")
		cy.contains("button", "Confirm").click()
		cy.wrap(null).should(() => expect(canvasStore.editingMode).to.equal("page"))
	})

	it("stays in the fragment while a drag or the context menu handles Escape", () => {
		cy.then(() => (canvasStore.isDragging = true))
		pressEscape()
		cy.then(() => (canvasStore.isDragging = false))
		pressEscape(document.getElementById("menu")!)
		cy.wait(10)
		cy.then(() => expect(canvasStore.editingMode).to.equal("fragment"))
	})
})
