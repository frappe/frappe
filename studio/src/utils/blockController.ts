import useStudioStore from "@/stores/studioStore"
import { CSSProperties } from "vue"
import Block from "./block"

import { StyleValue } from "@/types"

const store = useStudioStore()

type styleProperty = keyof CSSProperties

const blockController = {
	isAnyBlockSelected: () => {
		return store.selectedBlocks?.length || 0 > 0
	},
	multipleBlocksSelected: () => {
		return store.selectedBlocks && store.selectedBlocks.length > 1;
	},
	getFirstSelectedBlock: () => {
		return store.selectedBlocks[0] as Block;
	},
	getSelectedBlocks: () => {
		return store.selectedBlocks || [];
	},
	isRoot() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isRoot();
	},
	getParentBlock(): Block | null {
		return store.selectedBlocks[0]?.getParentBlock();
	},
	isFlex() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isFlex();
	},
	isGrid() {
		return blockController.isAnyBlockSelected() && blockController.getFirstSelectedBlock().isGrid();
	},
	setClasses: (classes: string[]) => {
		const block = store.selectedBlocks[0];
		if (!block) return;
		block.classes = classes;
	},
	getStyle: (style: styleProperty) => {
		let styleValue = "__initial__" as StyleValue;
		store.selectedBlocks.forEach((block) => {
			if (styleValue === "__initial__") {
				styleValue = block.getStyle(style);
			} else if (styleValue !== block.getStyle(style)) {
				styleValue = "Mixed";
			}
		});
		return styleValue;
	},
	setStyle: (style: styleProperty, value: StyleValue) => {
		store.selectedBlocks.forEach((block) => {
			block.setStyle(style, value);
		});
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
}

export default blockController