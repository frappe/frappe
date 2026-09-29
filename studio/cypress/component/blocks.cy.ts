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
