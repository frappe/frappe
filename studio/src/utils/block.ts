import { BlockOptions, BlockStyleMap } from "@/types"
import { clamp } from "@vueuse/core"
import { reactive, CSSProperties, nextTick } from 'vue'

import useStudioStore from "@/stores/studioStore";
import components from "@/data/components";
import { copyObject, getBlockCopy, kebabToCamelCase, numberToPx } from "./helpers";

export type styleProperty = keyof CSSProperties | `__${string}`;
class Block implements BlockOptions {
	componentId: string
	componentName: string
	componentProps: Record<string, any>
	blockName: string
	originalElement?: string | undefined
	children: BlockOptions[]
	parentBlock: Block | null
	baseStyles: BlockStyleMap
	mobileStyles: BlockStyleMap
	tabletStyles: BlockStyleMap

	constructor(options: BlockOptions) {
		this.componentName = options.componentName
		this.blockName = options.blockName || this.componentName
		this.originalElement = options.originalElement
		this.baseStyles = reactive(options.baseStyles || {})
		this.mobileStyles = reactive(options.mobileStyles || {});
		this.tabletStyles = reactive(options.tabletStyles || {});

		// generate ID
		if (!options.componentId) {
			this.componentId = this.generateComponentId()
		} else {
			this.componentId = options.componentId
		}

		// get component props
		if (!options.componentProps) {
			this.componentProps = copyObject(components.get(options.componentName)?.initialState)
		} else {
			this.componentProps = options.componentProps
		}

		// set up hierarchy
		this.parentBlock = options.parentBlock || null
		this.children = (options.children || []).map((child: BlockOptions) => {
			child.parentBlock = this;
			return reactive(new Block(child))
		})
	}

	generateComponentId(componentName?: string | null): string {
		return `${componentName || this.componentName}-${Math.random().toString(36).substring(2, 9)}`
	}

	addChild(child: BlockOptions, index?: number | null) {
		child.parentBlock = this
		if (index === undefined || index === null) {
			index = this.children.length
		}
		index = clamp(index, 0, this.children.length)

		this.children.splice(index, 0, child)
		child.selectBlock()
		return child
	}

	removeChild(child: Block) {
		const index = this.getChildIndex(child)
		if (index > -1) {
			this.children.splice(index, 1)
		}
	}

	getChildIndex(child: Block) {
		return this.children.findIndex((block) => block.componentId === child.componentId);
	}

	addChildAfter(child: BlockOptions, siblingBlock: Block) {
		const siblingIndex = this.getChildIndex(siblingBlock)
		return this.addChild(child, siblingIndex + 1)
	}

	hasChildren() {
		return this.children.length > 0
	}

	canHaveChildren() {
		return !["Dropdown", "FileUploader"].includes(this.componentName)
	}

	isRoot() {
		return this.componentId === "root" || this.originalElement === "body";
	}

	getParentBlock(): Block | null {
		return this.parentBlock || null;
	}

	getIcon() {
		if (this.isRoot()) return "Hash"
		return components.get(this.componentName)?.icon
	}

	getBlockDescription() {
		return this.blockName || this.originalElement
	}

	// styles
	getStyles(): BlockStyleMap {
		return { ...this.baseStyles }
	}

	getStyle(style: styleProperty) {
		return this.baseStyles[style]
	}

	setStyle(style: styleProperty, value: StyleValue) {
		const store = useStudioStore()
		let styleObj = this.baseStyles
		style = kebabToCamelCase(style) as styleProperty

		if (store.activeBreakpoint === "mobile") {
			styleObj = this.mobileStyles
		} else if (store.activeBreakpoint === "tablet") {
			styleObj = this.tabletStyles
		}
		if (value === null || value === "") {
			delete styleObj[style]
			return;
		}
		styleObj[style] = value
	}

	toggleVisibility() {
		if (this.getStyle("display") === "none") {
			this.setStyle("display", this.getStyle("__last_display") || "flex");
			this.setStyle("__last_display", null);
		} else {
			this.setStyle("__last_display", this.getStyle("display"));
			this.setStyle("display", "none");
		}
	}

	isVisible() {
		return this.getStyle("display") !== "none"
	}

	isFlex() {
		return this.getStyle("display") === "flex"
	}

	isGrid() {
		return this.getStyle("display") === "grid"
	}

	getPadding() {
		const padding = this.getStyle("padding") || "0px";

		const paddingTop = this.getStyle("paddingTop");
		const paddingBottom = this.getStyle("paddingBottom");
		const paddingLeft = this.getStyle("paddingLeft");
		const paddingRight = this.getStyle("paddingRight");

		if (!paddingTop && !paddingBottom && !paddingLeft && !paddingRight) {
			return padding;
		}

		if (
			paddingTop &&
			paddingBottom &&
			paddingTop === paddingBottom &&
			paddingTop === paddingRight &&
			paddingTop === paddingLeft
		) {
			return paddingTop;
		}

		if (paddingTop && paddingLeft && paddingTop === paddingBottom && paddingLeft === paddingRight) {
			return `${paddingTop} ${paddingLeft}`;
		} else {
			return `${paddingTop || padding} ${paddingRight || padding} ${paddingBottom || padding} ${
				paddingLeft || padding
			}`;
		}
	}

	setPadding(padding: string) {
		// reset padding
		this.setStyle("padding", null);
		this.setStyle("paddingTop", null);
		this.setStyle("paddingBottom", null);
		this.setStyle("paddingLeft", null);
		this.setStyle("paddingRight", null);

		if (!padding) {
			return;
		}

		const paddingArray = padding.split(" ");

		if (paddingArray.length === 1) {
			this.setStyle("padding", paddingArray[0]);
		} else if (paddingArray.length === 2) {
			this.setStyle("paddingTop", paddingArray[0]);
			this.setStyle("paddingBottom", paddingArray[0]);
			this.setStyle("paddingLeft", paddingArray[1]);
			this.setStyle("paddingRight", paddingArray[1]);
		} else if (paddingArray.length === 3) {
			this.setStyle("paddingTop", paddingArray[0]);
			this.setStyle("paddingLeft", paddingArray[1]);
			this.setStyle("paddingRight", paddingArray[1]);
			this.setStyle("paddingBottom", paddingArray[2]);
		} else if (paddingArray.length === 4) {
			this.setStyle("paddingTop", paddingArray[0]);
			this.setStyle("paddingRight", paddingArray[1]);
			this.setStyle("paddingBottom", paddingArray[2]);
			this.setStyle("paddingLeft", paddingArray[3]);
		}
	}

	setMargin(margin: string) {
		// reset margin
		this.setStyle("margin", null);
		this.setStyle("marginTop", null);
		this.setStyle("marginBottom", null);
		this.setStyle("marginLeft", null);
		this.setStyle("marginRight", null);

		if (!margin) {
			return;
		}

		const marginArray = margin.split(" ");

		if (marginArray.length === 1) {
			this.setStyle("margin", marginArray[0]);
		} else if (marginArray.length === 2) {
			this.setStyle("marginTop", marginArray[0]);
			this.setStyle("marginBottom", marginArray[0]);
			this.setStyle("marginLeft", marginArray[1]);
			this.setStyle("marginRight", marginArray[1]);
		} else if (marginArray.length === 3) {
			this.setStyle("marginTop", marginArray[0]);
			this.setStyle("marginLeft", marginArray[1]);
			this.setStyle("marginRight", marginArray[1]);
			this.setStyle("marginBottom", marginArray[2]);
		} else if (marginArray.length === 4) {
			this.setStyle("marginTop", marginArray[0]);
			this.setStyle("marginRight", marginArray[1]);
			this.setStyle("marginBottom", marginArray[2]);
			this.setStyle("marginLeft", marginArray[3]);
		}
	}

	getMargin() {
		const margin = this.getStyle("margin") || "0px";

		const marginTop = this.getStyle("marginTop");
		const marginBottom = this.getStyle("marginBottom");
		const marginLeft = this.getStyle("marginLeft");
		const marginRight = this.getStyle("marginRight");

		if (!marginTop && !marginBottom && !marginLeft && !marginRight) {
			return margin;
		}

		if (
			marginTop &&
			marginBottom &&
			marginTop === marginBottom &&
			marginTop === marginRight &&
			marginTop === marginLeft
		) {
			return marginTop;
		}

		if (marginTop && marginLeft && marginTop === marginBottom && marginLeft === marginRight) {
			return `${marginTop} ${marginLeft}`;
		} else {
			return `${marginTop || margin} ${marginRight || margin} ${marginBottom || margin} ${
				marginLeft || margin
			}`;
		}
	}

	// context menu
	duplicateBlock() {
		if (this.isRoot()) return

		const store = useStudioStore()
		const blockCopy = getBlockCopy(this)
		const parentBlock = this.getParentBlock()

		if (blockCopy.getStyle("position") === "absolute") {
			// shift the block a bit
			const left = numberToPx(blockCopy.getStyle("left"));
			const top = numberToPx(blockCopy.getStyle("top"));
			blockCopy.setStyle("left", `${left + 20}px`);
			blockCopy.setStyle("top", `${top + 20}px`);
		}

		let child = null as Block | null;
		if (parentBlock) {
			child = parentBlock.addChildAfter(blockCopy, this);
		} else {
			child = store.canvas?.getRootBlock().addChild(blockCopy) as Block;
		}
		nextTick(() => {
			if (child) {
				store.selectBlock(child);
			}
		});
	}

	selectBlock() {
		const store = useStudioStore();
		nextTick(() => {
			store.selectBlock(this, null);
		});
	}

	// component props
	setProp(propName: string, value: any) {
		this.componentProps[propName] = value
	}
}

export default Block