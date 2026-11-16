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
import { isReorderable } from "@/utils/useBlockReorder"
import { isMovable } from "@/utils/useBlockMove"
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

// root > column [A, B, C, empty, row [X, Y], positioned [pinned (absolute)]]
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
			// an absolute child sits to the RIGHT of the in-flow one, so it would form
			// its own cross-axis line if it were measured
			container(
				"positioned",
				{ position: "relative", flexDirection: "column", height: "160px", width: "100%", flexShrink: "0" },
				[
					container("pinned", {
						position: "absolute",
						top: "10px",
						left: "200px",
						width: "80px",
						height: "40px",
					}),
					leaf("anchored", { width: "120px" }),
				],
			),
			container("extras", { flexDirection: "column", gap: "8px", width: "100%", flexShrink: "0" }, [
				{
					componentId: "radios",
					componentName: "RadioGroup",
					componentProps: { modelValue: "a", orientation: "horizontal" },
					children: [
						{ componentId: "radio-a", componentName: "Radio", componentProps: { value: "a", label: "A" } },
						{ componentId: "radio-b", componentName: "Radio", componentProps: { value: "b", label: "B" } },
					],
				} as BlockOptions,
				// a component with an EMPTY named slot: its placeholder is the drop target
				{
					componentId: "popover",
					componentName: "Popover",
					componentProps: { side: "bottom", align: "start" },
					componentSlots: {
						trigger: {
							slotName: "trigger",
							slotId: "popover:trigger",
							parentBlockId: "popover",
							slotContent: [],
						},
					},
				} as BlockOptions,
				// in flow on desktop, pinned on mobile
				{
					...leaf("mobile-pinned"),
					mobileStyles: { position: "absolute", top: "0px", left: "0px" },
				} as BlockOptions,
			]),
		],
	)
}

const blockSelector = (id: string) =>
	`.__studio_component__[data-component-id="${id}"][data-breakpoint="desktop"]`
// the selected block's overlay; free move starts from here, as in builder
const editorSelector = (id: string) => `.editor[data-component-id="${id}"]`

function center(element: HTMLElement) {
	const rect = element.getBoundingClientRect()
	return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

function rectOf(id: string) {
	return document.querySelector(blockSelector(id))!.getBoundingClientRect()
}

// press on a block, cross the drag threshold, then hover the target point
function startDrag(
	sourceId: string,
	getTarget: () => { x: number; y: number },
	selector: (id: string) => string = blockSelector,
) {
	cy.get(selector(sourceId)).then(($el) => {
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

function select(id: string) {
	cy.get(blockSelector(id)).click({ force: true })
	cy.get(editorSelector(id)).should("exist")
}

describe("reordering blocks on the canvas by dragging", () => {
	let canvas: any
	const childIds = (id: string) => canvas.findBlock(id).children.map((child: Block) => child.componentId)
	// retries until the debounced tree watcher has recorded the entry
	const expectUndoEntries = (count: number) =>
		cy.wrap(null, { log: false }).should(() => expect(canvas.history.undoStack.length).to.equal(count))

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
			expect(childIds("column")).to.deep.equal(["B", "C", "A", "empty", "row", "positioned", "extras"])
			expect([...canvas.selectedBlockIds]).to.deep.equal(["A"])
		})
		expectUndoEntries(undoEntries + 1)
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
			expect(childIds("column")).to.deep.equal(["B", "C", "empty", "row", "positioned", "extras"])
			expect(canvas.findBlock("A").getParentBlock().componentId).to.equal("row")
		})
	})

	it("nests into an empty container from its centre and drags back out from its edge", () => {
		startDrag("B", () => center(document.querySelector(blockSelector("empty"))!))
		release()
		cy.then(() => {
			expect(childIds("empty")).to.deep.equal(["B"])
			expect(childIds("column")).to.deep.equal(["A", "C", "empty", "row", "positioned", "extras"])
		})

		// the (now apparently empty) parent is a no-op target, so its edge lands beside it
		startDrag("B", () => {
			const rect = rectOf("empty")
			return { x: rect.left + rect.width / 2, y: rect.top + 4 }
		})
		release()
		cy.then(() => {
			expect(childIds("empty")).to.deep.equal([])
			expect(childIds("column")).to.deep.equal(["A", "C", "B", "empty", "row", "positioned", "extras"])
		})
	})

	it("cancels with Escape and leaves the tree untouched", () => {
		startDrag("C", () => center(document.querySelector(blockSelector("A"))!))
		cy.get("#reorder-ghost").should("exist")
		cy.get("body").trigger("keydown", { key: "Escape", force: true })
		cy.get("#reorder-ghost").should("not.exist")
		release()
		cy.then(() =>
			expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row", "positioned", "extras"]),
		)
	})

	it("moves an absolutely positioned block freely instead of reordering it", () => {
		let undoEntries = 0
		cy.then(() => (undoEntries = canvas.history.undoStack.length))

		select("pinned")
		startDrag(
			"pinned",
			() => {
				const { x, y } = center(document.querySelector(blockSelector("pinned"))!)
				return { x: x + 100, y: y + 50 }
			},
			editorSelector,
		)
		cy.get("#reorder-ghost").should("not.exist")
		cy.then(() => {
			const pinned = canvas.findBlock("pinned")
			expect(pinned.getStyle("left")).to.equal("300px")
			expect(pinned.getStyle("top")).to.equal("60px")
			expect([...canvas.selectedBlockIds]).to.deep.equal(["pinned"])
		})
		release()
		cy.then(() => {
			expect(childIds("positioned")).to.deep.equal(["pinned", "anchored"])
			expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row", "positioned", "extras"])
		})
		expectUndoEntries(undoEntries + 1)
	})

	it("keeps family parts inside their family root", () => {
		startDrag("radio-a", () => center(document.querySelector(blockSelector("B"))!))
		cy.then(() => expect(useCanvasStore().reorderTarget.active).to.equal(false))
		release()
		cy.then(() => {
			expect(childIds("radios")).to.deep.equal(["radio-a", "radio-b"])
			expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row", "positioned", "extras"])
		})

		// reordering among siblings under the family root still works
		startDrag("radio-a", () => {
			const rect = rectOf("radio-b")
			return { x: rect.right - 4, y: rect.top + rect.height / 2 }
		})
		release()
		cy.then(() => expect(childIds("radios")).to.deep.equal(["radio-b", "radio-a"]))
	})

	it("picks the engine and the active breakpoint from the canvas being dragged in", () => {
		cy.then(() => {
			const block = canvas.findBlock("mobile-pinned")
			expect(isReorderable(block, "desktop")).to.equal(true)
			expect(isMovable(block, "desktop")).to.equal(false)
			expect(isReorderable(block, "mobile")).to.equal(false)
			expect(isMovable(block, "mobile")).to.equal(true)
		})
		select("pinned")
		// a stale active breakpoint must not leak into a drag on another canvas
		cy.then(() => canvas.setActiveBreakpoint("mobile"))
		startDrag(
			"pinned",
			() => {
				const { x, y } = center(document.querySelector(blockSelector("pinned"))!)
				return { x: x + 40, y }
			},
			editorSelector,
		)
		cy.then(() => expect(canvas.activeBreakpoint).to.equal("desktop"))
		release()
		cy.then(() => {
			const pinned = canvas.findBlock("pinned")
			expect(pinned.baseStyles.left).to.equal("240px")
			expect(pinned.mobileStyles.left).to.equal(undefined)
		})
	})

	it("drops onto an empty slot's placeholder into that slot", () => {
		const placeholder = () =>
			document.querySelector(
				'.__studio_component_slot__[data-slot-name="trigger"]:not(.__studio_component__)',
			)!
		cy.then(() => expect(placeholder()).to.exist)
		startDrag("C", () => center(placeholder() as HTMLElement))
		cy.then(() => {
			const target = useCanvasStore().reorderTarget
			expect(target.active).to.equal(true)
			expect(target.isSlotTarget).to.equal(true)
		})
		release()
		cy.then(() => {
			const popover = canvas.findBlock("popover")
			expect(popover.getSlotContent("trigger").map((block: Block) => block.componentId)).to.deep.equal(["C"])
			expect(canvas.findBlock("C").parentSlotName).to.equal("trigger")
			expect(childIds("popover")).to.deep.equal([])
			expect(childIds("column")).to.deep.equal(["A", "B", "empty", "row", "positioned", "extras"])
		})

		// the Popover is renderless, so dragging back out has no owner element to measure from
		startDrag("C", () => {
			const rect = rectOf("A")
			return { x: rect.left + rect.width / 2, y: rect.top + 4 }
		})
		release()
		cy.then(() => {
			expect(canvas.findBlock("popover").getSlotContent("trigger")).to.deep.equal([])
			expect(canvas.findBlock("C").parentSlotName).to.equal(undefined)
			expect(childIds("column")).to.deep.equal(["C", "A", "B", "empty", "row", "positioned", "extras"])
		})
	})

	it("ignores absolutely positioned siblings when measuring the drop slot", () => {
		startDrag("C", () => {
			const rect = rectOf("anchored")
			return { x: rect.left + rect.width / 2, y: rect.bottom + 20 }
		})
		release()
		cy.then(() => expect(childIds("positioned")).to.deep.equal(["pinned", "anchored", "C"]))
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
			expect(childIds("column")).to.deep.equal(["A", "B", "C", "empty", "row", "positioned", "extras"])
		})
	})
})
