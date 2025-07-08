import { CSSProperties } from "vue"
import Block from "./block"

import type { StyleValue, BlockStyleMap } from "@/types"
import useCanvasStore from "@/stores/canvasStore"

const canvasStore = useCanvasStore()

type styleProperty = keyof CSSProperties

const blockController = {
	clearSelection: () => {
		canvasStore.activeCanvas?.clearSelection()
	},
	isAnyBlockSelected: () => {
		return canvasStore.activeCanvas?.selectedBlocks.length || 0 > 0
	},
	multipleBlocksSelected: () => {
		return canvasStore.activeCanvas?.selectedBlocks && canvasStore.activeCanvas?.selectedBlocks.length > 1
	},
	getFirstSelectedBlock: () => {
		return canvasStore.activeCanvas?.selectedBlocks[0] as Block
	},
	getSelectedBlocks: () => {
		return canvasStore.activeCanvas?.selectedBlocks || []
	},
	isRoot() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isRoot();
	},
	getParentBlock() {
		return canvasStore.activeCanvas?.selectedBlocks[0]?.getParentBlock();
	},
	isFlex() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isFlex();
	},
	isGrid() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isGrid();
	},
	getClasses: () => {
		let classes = [] as string[]
		if (blockController.isAnyBlockSelected()) {
			classes = blockController.getFirstSelectedBlock().getClasses() || [];
		}
		return classes
	},
	setClasses: (classes: string[]) => {
		const block = canvasStore.activeCanvas?.selectedBlocks[0]
		if (!block) return
		block.classes = classes
	},
	getStyle: (style: styleProperty) => {
		let styleValue = "__initial__" as StyleValue;
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			if (styleValue === "__initial__") {
				styleValue = block.getStyle(style);
			} else if (styleValue !== block.getStyle(style)) {
				styleValue = "Mixed";
			}
		});
		return styleValue;
	},
	setStyle: (style: styleProperty, value: StyleValue) => {
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			block.setStyle(style, value);
		});
	},
	setBaseStyle: (style: styleProperty, value: StyleValue) => {
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			block.setBaseStyle(style, value);
		});
	},
	getRawStyles: () => {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().getRawStyles()
	},
	setRawStyles: (rawStyles: BlockStyleMap) => {
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			Object.keys(block.rawStyles).forEach((key) => {
				if (!rawStyles[key]) {
					delete block.rawStyles[key];
				}
			})
			Object.assign(block.rawStyles, rawStyles)
		})
	},
	getPadding: () => {
		let padding = "__initial__" as StyleValue;
		blockController.getSelectedBlocks().forEach((block) => {
			if (padding === "__initial__") {
				padding = block.getPadding();
			} else if (padding !== block.getPadding()) {
				padding = "Mixed";
			}
		});
		return padding;
	},
	setPadding: (value: string) => {
		blockController.getSelectedBlocks().forEach((block) => {
			block.setPadding(value);
		});
	},
	getMargin: () => {
		let margin = "__initial__" as StyleValue;
		blockController.getSelectedBlocks().forEach((block) => {
			if (margin === "__initial__") {
				margin = block.getMargin();
			} else if (margin !== block.getMargin()) {
				margin = "Mixed";
			}
		});
		return margin;
	},
	setMargin: (value: string) => {
		blockController.getSelectedBlocks().forEach((block) => {
			block.setMargin(value);
		});
	},
	getKeyValue: (key: "visibilityCondition") => {
		let keyValue = "__initial__" as StyleValue | undefined;
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			if (keyValue === "__initial__") {
				keyValue = block[key];
			} else if (keyValue !== block[key]) {
				keyValue = "Mixed";
			}
		});
		return keyValue;
	},
	setKeyValue: (key: "visibilityCondition", value: string) => {
		canvasStore.activeCanvas?.selectedBlocks.forEach((block) => {
			block[key] = value;
		});
	},
}

export default blockController