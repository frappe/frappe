// Imported first so Pinia is active before StudioCanvas (and its top-level
// useCanvasStore() calls) are evaluated below.
import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { createRouter, createMemoryHistory } from "vue-router"
import { resourcesPlugin } from "frappe-ui"
import { spritePlugin } from "frappe-ui/icons"

import StudioCanvas from "@/components/StudioCanvas.vue"
import Block from "@/utils/block"
import componentsData, { COMPONENTS } from "@/data/components"
import { getBlockInstance, getComponentBlock } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { registerGlobalComponents } from "@/globals"
import useCanvasStore from "@/stores/canvasStore"
import type { FrappeUIComponent } from "@/types"

// Skipped: these render real data and need a Frappe backend, which isn't available
// in the component-test environment.
const DATA_DEPENDENT = ["ListView", "Link", "Filter", "Calendar", "NumberChart", "AxisChart", "DonutChart"]
// Skipped: these don't render as a plain child on the page canvas.
// Dialog opens in fragment mode on drop; Repeater needs a data source to render rows.
const SPECIAL = ["Dialog", "Repeater"]
const SKIP = new Set([...DATA_DEPENDENT, ...SPECIAL])

const componentsToTest = componentsData.list.filter((component) => !SKIP.has(component.name))

// Mirrors the drop branching in useCanvasDropZone.onDrop
function createBlock(component: FrappeUIComponent): Block {
	return component.blockTemplate
		? getBlockInstance(getBlockTemplate(component.blockTemplate as any))
		: getComponentBlock(component.name)
}

describe("dropping frappe-ui components on the canvas", () => {
	// exposed StudioCanvas instance (defineExpose) used as canvasStore.activeCanvas
	let canvas: any

	beforeEach(() => {
		// block prop/slot init reads Block.components (done in main.ts in the real app)
		Block.setComponents(COMPONENTS)

		setActivePinia(pinia)
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/", component: { template: "<div />" } }],
		})

		// fresh empty page (body block) as the canvas root
		const rootBlock = getBlockInstance(getBlockTemplate("body"))

		cy.mount(StudioCanvas, {
			props: { componentTree: rootBlock },
			global: {
				plugins: [pinia, router, resourcesPlugin, spritePlugin, { install: registerGlobalComponents }],
			},
		}).then(({ wrapper }) => {
			canvas = wrapper.vm
			// the editor registers the mounted canvas as active (see StudioPage.vue)
			useCanvasStore().activeCanvas = canvas
		})
	})

	componentsToTest.forEach((component) => {
		it(`renders ${component.name} with a data-component-id and selects it on click`, () => {
			let block: Block

			cy.then(() => {
				// same call the drop performs; addChild returns the rendered block
				block = canvas.rootComponent.addChild(createBlock(component))
				// addChild auto-selects; clear so the click below is what selects the block
				canvas.clearSelection()
			})

			// (a) the dropped component is rendered and carries a data-component-id
			cy.then(() => {
				cy.get(`[data-component-id="${block.componentId}"]`)
					.should("exist")
					// (b) clicking the element selects the block
					.first()
					.click({ force: true })
			})

			cy.then(() => {
				expect([...canvas.selectedBlockIds]).to.include(block.componentId)
			})
		})
	})
})
