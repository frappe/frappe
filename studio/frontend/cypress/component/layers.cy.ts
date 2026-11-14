import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import ComponentLayers from "@/components/ComponentLayers.vue"
import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { registerGlobalComponents } from "@/globals"
import type { BlockOptions } from "@/types"

function container(componentId: string, children: BlockOptions[] = []) {
	return { componentId, componentName: "container", originalElement: "div", children } as BlockOptions
}

// root > outer > inner > leaf, and a popover whose trigger slot holds slotted > slotted-leaf
function buildTree() {
	return [
		container("outer", [container("inner", [container("leaf")])]),
		{
			componentId: "popover",
			componentName: "Popover",
			componentSlots: {
				trigger: {
					slotName: "trigger",
					slotId: "popover:trigger",
					parentBlockId: "popover",
					slotContent: [getBlockInstance(container("slotted", [container("slotted-leaf")]))],
				},
			},
		} as BlockOptions,
	]
}

const layer = (id: string) => `[data-component-layer-id="${id}"]`

describe("expand and collapse all layers", () => {
	let layers: InstanceType<typeof ComponentLayers>

	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
		const rootBlock = getBlockInstance({ ...getBlockTemplate("body"), children: buildTree() })
		cy.mount(ComponentLayers as any, {
			props: { blocks: [rootBlock] },
			global: { plugins: [pinia, resourcesPlugin, { install: registerGlobalComponents }] },
		}).then(({ wrapper }) => {
			layers = wrapper.vm as InstanceType<typeof ComponentLayers>
		})
		cy.get(layer("outer")).should("be.visible")
		cy.get(layer("inner")).should("not.be.visible")
	})

	it("expands every nested block and slot, then collapses back to the top level", () => {
		cy.then(() => layers.expandAll())
		cy.get(layer("leaf")).should("be.visible")
		cy.get(layer("slotted-leaf")).should("be.visible")
		cy.then(() => layers.collapseAll())
		cy.get(layer("outer")).should("be.visible")
		cy.get(layer("inner")).should("not.be.visible")
		cy.get(layer("slotted")).should("not.exist")
		// expanding again after a collapse reaches the same depth
		cy.then(() => layers.expandAll())
		cy.get(layer("leaf")).should("be.visible")
		cy.get(layer("slotted-leaf")).should("be.visible")
	})
})
