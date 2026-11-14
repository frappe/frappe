import { pinia } from "../support/component"

import { setActivePinia } from "pinia"

import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { canPasteStylesTo, copyBlockStyles, pasteBlockStyles } from "@/utils/styleCopyPaste"
import type { BlockOptions } from "@/types"

function container(componentId: string, styles: Partial<BlockOptions> = {}) {
	return getBlockInstance({ componentId, componentName: "container", originalElement: "div", ...styles })
}

const root = () => getBlockInstance({ ...getBlockTemplate("body") })

describe("copy and paste block styles", () => {
	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
	})

	it("merges every breakpoint's styles into another block, not back into the source", () => {
		const source = container("source", {
			baseStyles: { color: "red", padding: "8px" },
			tabletStyles: { padding: "4px" },
			mobileStyles: { display: "none" },
		})
		const target = container("target", { baseStyles: { color: "blue", margin: "2px" } })

		copyBlockStyles(source)
		expect(canPasteStylesTo(source)).to.be.false
		pasteBlockStyles(target)

		expect(target.baseStyles).to.deep.equal({ color: "red", margin: "2px", padding: "8px" })
		expect(target.tabletStyles).to.deep.equal({ padding: "4px" })
		expect(target.mobileStyles).to.deep.equal({ display: "none" })
	})

	it("pastes one page's root styles onto another page's root", () => {
		const sourceRoot = root()
		sourceRoot.setStyle("background", "black")
		const targetRoot = root()

		copyBlockStyles(sourceRoot)
		pasteBlockStyles(targetRoot)

		expect(targetRoot.baseStyles.background).to.equal("black")
	})
})

describe("slot content", () => {
	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
	})

	// Studio's own writers store { slotName, slotContent }. JSON written by hand often skips
	// the wrapper, and dropping it would lose the whole slot without an error.
	it("keeps slot content written as a bare array", () => {
		const block = getBlockInstance({
			componentId: "repeater-1",
			componentName: "Repeater",
			componentSlots: {
				default: [{ componentId: "row-1", componentName: "container", originalElement: "div" }],
			} as any,
		})

		const slot = block.componentSlots.default
		expect(slot.slotName).to.equal("default")
		expect(slot.slotId).to.equal("repeater-1:default")
		expect(slot.parentBlockId).to.equal("repeater-1")
		expect(slot.slotContent).to.have.length(1)
		expect(slot.slotContent[0]).to.be.instanceOf(Block)
		expect(slot.slotContent[0].componentId).to.equal("row-1")
	})
})
