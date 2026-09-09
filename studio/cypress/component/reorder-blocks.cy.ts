import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { createRouter, createMemoryHistory } from "vue-router"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import StudioCanvas from "@/components/StudioCanvas.vue"
import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { registerGlobalComponents } from "@/globals"
import useCanvasStore from "@/stores/canvasStore"
import type { BlockOptions } from "@/types"

const HISTORY_DEBOUNCE = 150

function container(componentId: string, baseStyles: Record<string, string>, children: BlockOptions[] = []) {
	return {
		componentId,
		componentName: "container",
		originalElement: "div",
		baseStyles,
		children,
	} as BlockOptions
}

function leaf(componentId: string, extraStyles: Record<string, string> = {}) {
	return container(componentId, { height: "60px", width: "100%", flexShrink: "0", ...extraStyles })
}

// root > column [A, B, C, empty, row [X, Y]]
function buildTree() {
	return container(
		"column",
		{ display: "flex", flexDirection: "column", width: "100%", gap: "8px", padding: "8px" },
		[
			leaf("A"),
			leaf("B"),
			leaf("C"),
			container("empty", { display: "flex", height: "120px", width: "100%", flexShrink: "0" }),
			container("row", { display: "flex", flexDirection: "row", gap: "8px", height: "80px", width: "100%" }, [
				leaf("X", { width: "200px", height: "100%" }),
				leaf("Y", { width: "200px", height: "100%" }),
			]),
		],
	)
}

const blockSelector = (id: string) =>
	`.__studio_component__[data-component-id="${id}"][data-breakpoint="desktop"]`

function center(element: HTMLElement) {
	const rect = element.getBoundingClientRect()
	return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

function rectOf(id: string) {
	return document.querySelector(blockSelector(id))!.getBoundingClientRect()
}

// press on a block, cross the drag threshold, then hover the target point
function startDrag(sourceId: string, getTarget: () => { x: number; y: number }) {
	cy.get(blockSelector(sourceId)).then(($el) => {
		const { x, y } = center($el[0])
		cy.wrap($el).trigger("mousedown", { button: 0, clientX: x, clientY: y, force: true })
		cy.get("body").trigger("mousemove", { clientX: x + 10, clientY: y + 10, force: true })
	})
	cy.then(() => {
		const target = getTarget()
		cy.get("body").trigger("mousemove", { clientX: target.x, clientY: target.y, force: true })
	})
}

function release() {
	cy.get("body").trigger("mouseup", { force: true })
}

describe("reordering blocks on the canvas by dragging", () => {
	let canvas: any
	const childIds = (id: string) => canvas.findBlock(id).children.map((child: Block) => child.componentId)

	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/", component: { template: "<div />" } }],
		})
		const rootBlock = getBlockInstance({ ...getBlockTemplate("body"), children: [buildTree()] })

		cy.viewport(1440, 900)
		cy.mount(StudioCanvas as any, {
			props: { componentTree: rootBlock },
			global: {
				plugins: [pinia, router, resourcesPlugin, { install: registerGlobalComponents }],
			},
		}).then(({ wrapper }) => {
			canvas = wrapper.vm
			useCanvasStore().activeCanvas = canvas
		})
		cy.then(() => {
			canvas.canvasProps.scale = 1
			canvas.canvasProps.translateX = 0
			canvas.canvasProps.translateY = 0
		})
		cy.get(blockSelector("Y")).should("exist")
		cy.wait(HISTORY_DEBOUNCE)
	})

	it("reorders a block among its siblings in a column and records one history entry", () => {
		let undoEntries = 0
		cy.then(() => (undoEntries = canvas.history.undoStack.length))

		startDrag("A", () => {
			const rect = rectOf("C")
			return { x: rect.left + rect.width / 2, y: rect.bottom - 5 }
		})
		cy.get("#reorder-ghost").should("exist")
		cy.get(blockSelector("A")).should("have.css", "visibility", "hidden")
		cy.then(() => {
			const target = useCanvasStore().reorderTarget
			expect(target.active).to.equal(true)
			expect(target.isSameContainer).to.equal(true)
			expect(target.line?.orientation).to.equal("horizontal")
		})
		release()

		cy.get("#reorder-ghost").should("not.exist")
		cy.get(blockSelector("A")).should("have.css", "visibility", "visible")
		cy.then(() => {
			expect(childIds("column")).to.deep.equal(["B", "C", "A", "empty", "row"])
			expect([...canvas.selectedBlockIds]).to.deep.equal(["A"])
		})
		cy.wait(HISTORY_DEBOUNCE)
		cy.then(() => expect(canvas.history.undoStack.length).to.equal(undoEntries + 1))
	})

	it("moves a block into a row container between two siblings", () => {
		startDrag("A", () => {
			const x = rectOf("X")
			const y = rectOf("Y")
			return { x: (x.right + y.left) / 2, y: x.top + x.height / 2 }
		})
		cy.then(() => {
			const target = useCanvasStore().reorderTarget
			expect(target.isSameContainer).to.equal(false)
			expect(target.line?.orientation).to.equal("vertical")
		})
		release()
		cy.then(() => {
			expect(childIds("row")).to.deep.equal(["X", "A", "Y"])
			expect(childIds("column")).to.deep.equal(["B", "C", "empty", "row"])
			expect(canvas.findBlock("A").getParentBlock().componentId).to.equal("row")
		})
	})

	it("nests into an empty container from its centre and drags back out from its edge", () => {
		startDrag("B", () => center(document.querySelector(blockSelector("empty"))!))
		release()
		cy.then(() => {
			expect(childIds("empty")).to.deep.equal(["B"])
			expect(childIds("column")).to.deep.equal(["A", "C", "empty", "row"])
		})

		// the (now apparently empty) parent is a no-op target, so its edge lands beside it
		startDrag("B", () => {
			const rect = rectOf("empty")
			return { x: rect.left + rect.width / 2, y: rect.top + 4 }
		})
		release()
		cy.then(() => {
			expect(childIds("empty")).to.deep.equal([])
			expect(childIds("column")).to.deep.equal(["A", "C", "B", "empty", "row"])
		})
	})

	it("cancels with Escape and leaves the tree untouched", () => {
		startDrag("C", () => center(document.querySelector(blockSelector("A"))!))
		cy.get("#reorder-ghost").should("exist")
		cy.get("body").trigger("keydown", { key: "Escape", force: true })
		cy.get("#reorder-ghost").should("not.exist")
		release()
		cy.then(() => expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row"]))
	})

	it("does not start a drag on a plain click", () => {
		cy.get(blockSelector("B")).then(($el) => {
			const { x, y } = center($el[0])
			cy.wrap($el).trigger("mousedown", { button: 0, clientX: x, clientY: y, force: true })
			cy.get("body").trigger("mousemove", { clientX: x + 1, clientY: y + 1, force: true })
		})
		cy.get("#reorder-ghost").should("not.exist")
		release()
		cy.get(blockSelector("B")).click({ force: true })
		cy.then(() => {
			expect([...canvas.selectedBlockIds]).to.deep.equal(["B"])
			expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row"])
		})
	})
})
