import { pinia } from "../support/component"

import { setActivePinia } from "pinia"

import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import { canPasteStylesTo, copyBlockStyles, pasteBlockStyles } from "@/utils/blockCopyPaste"
import type { BlockOptions } from "@/types"

function container(componentId: string, styles: Partial<BlockOptions> = {}) {
	return getBlockInstance({ componentId, componentName: "container", originalElement: "div", ...styles })
}

describe("copy and paste block styles", () => {
	beforeEach(() => {
		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
	})

	it("merges every breakpoint's styles into the target block", () => {
		const source = container("source", {
			baseStyles: { color: "red", padding: "8px" },
			tabletStyles: { padding: "4px" },
			mobileStyles: { display: "none" },
		})
		const target = container("target", { baseStyles: { color: "blue", margin: "2px" } })

		copyBlockStyles(source)
		expect(canPasteStylesTo(target)).to.be.true
		pasteBlockStyles(target)

		expect(target.baseStyles).to.deep.equal({ color: "red", margin: "2px", padding: "8px" })
		expect(target.tabletStyles).to.deep.equal({ padding: "4px" })
		expect(target.mobileStyles).to.deep.equal({ display: "none" })
	})

	it("does not paste onto the block the styles came from", () => {
		const source = container("source", { baseStyles: { color: "red" } })
		copyBlockStyles(source)
		expect(canPasteStylesTo(source)).to.be.false
	})
})
