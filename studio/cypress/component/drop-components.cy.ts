import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { createRouter, createMemoryHistory } from "vue-router"
// @ts-ignore
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

const DATA_DEPENDENT = ["ListView", "Link", "Filter", "Calendar", "NumberChart", "AxisChart", "DonutChart", "Repeater"]
const FLOATING = ["Dialog", "Tooltip", "ContextMenu"]
const SKIP = new Set([...DATA_DEPENDENT, ...FLOATING])

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

		const rootBlock = getBlockInstance(getBlockTemplate("body"))

		cy.viewport(1440, 900)
		cy.mount(StudioCanvas as any, {
			props: { componentTree: rootBlock },
			global: {
				plugins: [pinia, router, resourcesPlugin, spritePlugin, { install: registerGlobalComponents }],
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
