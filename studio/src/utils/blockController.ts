import useStore from "@/store"
import { CSSProperties, nextTick } from "vue"
import Block from "./block"

const store = useStore()

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
}

export default blockController