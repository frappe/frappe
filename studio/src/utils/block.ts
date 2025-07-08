import type { BlockOptions, BlockStyleMap, CompletionSource, Slot } from "@/types"
import { clamp } from "@vueuse/core"
import { reactive, CSSProperties, nextTick } from 'vue'

import useCanvasStore from "@/stores/canvasStore"
import LucideHash from "~icons/lucide/hash"
import LucideAppWindow from "~icons/lucide/app-window"

import { copyObject, generateId, getBlockCopy, isObjectEmpty, kebabToCamelCase, numberToPx } from "./helpers";

import type { StyleValue, FrappeUIComponents } from "@/types"
import type { ComponentEvent } from "@/types/ComponentEvent"

export type styleProperty = keyof CSSProperties | `__${string}`;
class Block implements BlockOptions {
	componentId: string
	componentName: string
	componentProps: Record<string, any>
	componentSlots: Record<string, Slot>
	componentEvents: Record<string, any>
	blockName: string
	children: Block[]
	parentBlock: Block | null
	baseStyles: BlockStyleMap
	rawStyles: BlockStyleMap
	mobileStyles: BlockStyleMap
	tabletStyles: BlockStyleMap
	visibilityCondition?: string
	originalElement?: string
	classes?: string[]
	parentSlotName?: string
	// temporary property
	repeaterDataItem?: Record<string, any> | null

	// @editor-only
	private static components: FrappeUIComponents | null = null

	constructor(options: BlockOptions) {
		this.componentName = options.componentName
		this.blockName = options.blockName || this.componentName
		this.originalElement = options.originalElement
		this.baseStyles = reactive(options.baseStyles || {})
		this.rawStyles = reactive(options.rawStyles || {});
		this.mobileStyles = reactive(options.mobileStyles || {})
		this.tabletStyles = reactive(options.tabletStyles || {})
		this.classes = options.classes || []
		this.visibilityCondition = options.visibilityCondition

		// generate ID
		if (!options.componentId) {
			this.componentId = this.generateComponentId()
		} else {
			this.componentId = options.componentId
		}

		// get component props
		if (!options.componentProps) {
			this.componentProps = copyObject(Block.components?.[options.componentName]?.initialState)
		} else {
			this.componentProps = options.componentProps
		}

		this.componentSlots = options.componentSlots || {}
		if (!options.componentSlots) {
			let slots = Block.components?.[options.componentName]?.initialSlots || []
			slots.forEach((slot) => {
				this.addSlot(slot)
			})
		}

		this.componentEvents = options.componentEvents || {}
		this.initializeSlots()

		// Define as non-reactive property
		Object.defineProperty(this, "repeaterDataItem", {
			value: options.repeaterDataItem || null,
			writable: true,
			enumerable: false,
			configurable: true
		})

		if (options.parentSlotName) {
			this.parentSlotName = options.parentSlotName
		}

		// set up hierarchy
		this.parentBlock = options.parentBlock || null
		this.children = (options.children || []).map((child: BlockOptions) => {
			child.parentBlock = this;
			return reactive(new Block(child))
		})
	}

	static setComponents(components: FrappeUIComponents) {
		Block.components = components
	}

	static getComponents() {
		return Block.components
	}

	generateComponentId(componentName?: string | null): string {
		return `${componentName || this.componentName}-${generateId()}`
	}

	deleteBlock() {
		const parentBlock = this.getParentBlock()
		if (parentBlock) {
			parentBlock.removeChild(this)
		}
	}

	addChild(child: BlockOptions, index?: number | null) {
		if (child.parentSlotName) {
			return this.updateSlot(child.parentSlotName, child, index)
		}

		index = this.getValidIndex(index, this.children.length)
		const childBlock = reactive(new Block(child))
		childBlock.parentBlock = this
		this.children.splice(index, 0, childBlock)
		childBlock.selectBlock()
		return childBlock
	}

	removeChild(child: Block) {
		const index = this.getChildIndex(child)
		if (index === -1) return

		if (child.isSlotBlock()) {
			let slotContent = this.getSlotContent(child.parentSlotName!)
			if (!Array.isArray(slotContent)) return

			if (slotContent.length === 1) {
				this.updateSlot(child.parentSlotName!, "")
			} else {
				slotContent.splice(index, 1)
			}
		} else {
			this.children.splice(index, 1)
		}
	}

	replaceChild(child: Block, newChild: Block) {
		newChild.parentBlock = this
		const index = this.getChildIndex(child)
		if (index > -1) {
			// This is not triggering the reactivity even though the child object is reactive
			// this.children.splice(index, 1, newChild);
			this.removeChild(child)
			this.addChild(newChild, index)
		}
	}

	getChildIndex(child: Block) {
		if (child.parentSlotName) {
			return (
				this.getSlotContent(child.parentSlotName) as Block[]
			)?.findIndex((block) => block.componentId === child.componentId)
		}
		return this.children.findIndex((block) => block.componentId === child.componentId)
	}

	getValidIndex(index: number | null | undefined, arrayLength: number): number {
		if (index === undefined || index === null) {
			return arrayLength
		}
		return clamp(index, 0, arrayLength)
	  }

	addChildAfter(child: BlockOptions, siblingBlock: Block) {
		const siblingIndex = this.getChildIndex(siblingBlock)
		return this.addChild(child, siblingIndex + 1)
	}

	hasChildren() {
		return this.children.length > 0
	}

	canHaveChildren() {
		return ![
			"Dropdown",
			"FileUploader",
			"Divider",
			"FeatherIcon",
			"Avatar",
			// input components
			"Autocomplete",
			"Checkbox",
			"DatePicker",
			"DateTimePicker",
			"DateRangePicker",
			"Input",
			"Select",
			"Switch",
			"Textarea",
			"TextEditor",
			// studio components
			"Audio",
			"ImageView",
			"TextBlock",
		].includes(this.componentName)
	}

	isRoot() {
		return this.componentId === "root" || this.originalElement === "body";
	}

	isContainer() {
		return this.originalElement === "div"
	}

	getParentBlock(): Block | null {
		return this.parentBlock || null;
	}

	getSiblingBlock(direction: "next" | "previous") {
		const parentBlock = this.getParentBlock();
		let sibling = null as Block | null;
		if (parentBlock) {
			const index = parentBlock.getChildIndex(this);
			if (direction === "next") {
				sibling = parentBlock.children[index + 1];
			} else {
				sibling = parentBlock.children[index - 1];
			}
			if (sibling) {
				return sibling;
			}
		}
		return null;
	}

	getIcon() {
		if (this.isRoot()) return LucideHash
		if (this.componentName === "container") return LucideAppWindow
		return Block.components?.[this.componentName]?.icon
	}

	getBlockDescription() {
		return this.blockName || this.originalElement
	}

	editInFragmentMode() {
		return Block.components?.[this.componentName]?.editInFragmentMode
	}

	getProxyComponent() {
		return Block.components?.[this.componentName]?.proxyComponent
	}

	// styles
	setBaseStyle(style: styleProperty, value: StyleValue) {
		style = kebabToCamelCase(style as string) as styleProperty
		this.baseStyles[style] = value
	}

	getStyles(breakpoint: string = "desktop"): BlockStyleMap {
		let styleObj = {}

		styleObj = { ...this.baseStyles }
		if (["mobile", "tablet"].includes(breakpoint)) {
			styleObj = { ...styleObj, ...this.tabletStyles }
			if (breakpoint === "mobile") {
				styleObj = { ...styleObj, ...this.mobileStyles }
			}
		}
		styleObj = { ...styleObj, ...this.rawStyles }
		return styleObj
	}

	getStyle(style: styleProperty, breakpoint?: string | null) {
		const canvasStore = useCanvasStore();
		breakpoint = breakpoint || canvasStore.activeCanvas?.activeBreakpoint
		let styleValue = undefined as StyleValue
		if (breakpoint === "mobile") {
			styleValue = this.mobileStyles[style] || this.tabletStyles[style] || this.baseStyles[style]
		} else if (breakpoint === "tablet") {
			styleValue = this.tabletStyles[style] || this.baseStyles[style]
		} else {
			styleValue = this.baseStyles[style]
		}

		return styleValue
	}

	setStyle(style: styleProperty, value: StyleValue) {
		const canvasStore = useCanvasStore()
		let styleObj = this.baseStyles
		style = kebabToCamelCase(style) as styleProperty

		if (canvasStore.activeCanvas?.activeBreakpoint === "mobile") {
			styleObj = this.mobileStyles
		} else if (canvasStore.activeCanvas?.activeBreakpoint === "tablet") {
			styleObj = this.tabletStyles
		}
		if (value === null || value === "") {
			delete styleObj[style]
			return;
		}
		styleObj[style] = value
	}

	hasOverrides(breakpoint: string) {
		if (breakpoint === "mobile") {
			return Object.keys(this.mobileStyles).length > 0
		}
		if (breakpoint === "tablet") {
			return Object.keys(this.tabletStyles).length > 0
		}
		return false
	}

	resetOverrides(breakpoint: string) {
		if (breakpoint === "mobile") {
			this.mobileStyles = {}
		}
		if (breakpoint === "tablet") {
			this.tabletStyles = {}
		}
	}

	getRawStyles() {
		return { ...this.rawStyles }
	}

	getClasses() {
		return [...this.classes || []]
	}

	toggleVisibility(show: boolean | null = null) {
		if ((this.getStyle("display") === "none" && show !== false) || (show === true)) {
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

		const canvasStore = useCanvasStore()
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
			child = parentBlock.addChildAfter(blockCopy, this) as Block;
		} else {
			child = canvasStore.activeCanvas?.getRootBlock().addChild(blockCopy) as Block;
		}
		nextTick(() => {
			if (child) {
				child.selectBlock()
			}
		});
	}

	selectBlock() {
		const canvasStore = useCanvasStore();
		nextTick(() => {
			canvasStore.activeCanvas?.selectBlock(this, null);
		});
	}

	// component props
	setProp(propName: string, value: any) {
		this.componentProps[propName] = value
	}

	// component slots
	initializeSlots() {
		Object.entries(this.componentSlots).forEach(([slotName, slot]) => {
			if (!slot.slotId) {
				slot.slotId = this.generateSlotId(slotName)
			}
			slot.parentBlockId = this.componentId

			if (Array.isArray(slot.slotContent)) {
				slot.slotContent = slot.slotContent.map((block) => {
					block.parentBlock = this
					return reactive(new Block(block))
				})
			}
		})
	}

	addSlot(slotName: string) {
		this.componentSlots[slotName] = {
			slotName: slotName,
			slotId: this.generateSlotId(slotName),
			slotContent: "",
			parentBlockId: this.componentId
		}
		nextTick(() => {
			const canvasStore = useCanvasStore()
			canvasStore.activeCanvas?.selectSlot(this.componentSlots[slotName])
		})
	}

	updateSlot(slotName: string, content: string | Block | BlockOptions, index?: number | null) {
		if (typeof content === "string") {
			this.componentSlots[slotName].slotContent = content
		} else {
			if (!Array.isArray(this.componentSlots[slotName].slotContent)) {
				this.componentSlots[slotName].slotContent = []
			}

			// for top-level blocks inside a slot
			content.parentSlotName = slotName
			content.parentBlock = this
			const slotContent = this.componentSlots[slotName].slotContent as Block[]
			index = this.getValidIndex(index, slotContent.length)
			const childBlock = reactive(new Block(content))
			slotContent.splice(index, 0, childBlock)
			childBlock.selectBlock()
			return childBlock
		}
	}

	removeSlot(slotName: string) {
		delete this.componentSlots[slotName]
	}

	getSlot(slotName: string) {
		return this.componentSlots[slotName]
	}

	getSlotContent(slotName: string) {
		return this.componentSlots[slotName]?.slotContent
	}

	hasComponentSlots() {
		return !isObjectEmpty(this.componentSlots)
	}

	generateSlotId(slotName: string) {
		return `${this.componentId}:${slotName}`
	}

	isSlotEditable(slot: Slot | undefined | null) {
		if (!slot) return false

		return Boolean(
			!this.isRoot()
			&& slot.slotId
			&& typeof slot.slotContent === "string"
		)
	}

	isSlotBlock() {
		return Boolean(this.parentSlotName)
	}

	// repeater
	isRepeater() {
		return this.componentName === "Repeater"
	}

	setRepeaterDataItem(repeaterDataItem: Record<string, any>) {
		// temporarily set repeater data item on selected block for autocompletions
		this.repeaterDataItem = repeaterDataItem
	}

	getRepeaterDataCompletions(): CompletionSource[] {
		if (this.repeaterDataItem) {
			return [
				{
					item: this.repeaterDataItem,
					completion: {
						label: "dataItem",
						type: "data",
						detail: "Repeater Data Item",
					}
				},
				{
					item: "dataIndex",
					completion: {
						label: "dataIndex",
						type: "data",
						detail: "Repeater Data Index",
					}
				}
			]
		}
		return []
	}

	// events
	addEvent(event: ComponentEvent) {
		this.componentEvents[event.event] = event
	}

	updateEvent(event: ComponentEvent) {
		if (event.oldEvent && event.event !== event.oldEvent) {
			this.removeEvent(event.oldEvent)
			delete event.oldEvent
		}
		this.componentEvents[event.event] = event
	}

	removeEvent(eventName: string) {
		delete this.componentEvents[eventName]
	}
}

export default Block