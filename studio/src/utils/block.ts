import type { BlockOptions, BlockStyleMap, CompletionSource, Slot, SlotScope } from "@/types"
import { clamp } from "@vueuse/core"
import { reactive, CSSProperties, nextTick } from 'vue'

import useCanvasStore from "@/stores/canvasStore"
import useComponentStore from "@/stores/componentStore"
import LucideHash from "~icons/lucide/hash"
import LucideAppWindow from "~icons/lucide/app-window"
import LucideBox from "~icons/lucide/box"
import LucideCode from "~icons/lucide/code"

import { generateId, isObjectEmpty, kebabToCamelCase, numberToPx } from "./helpers";
import { copyObject, getBlockCopy, getComponentBlock } from "@/utils/serializer"
import { componentHasDefaultSlot, getComponentSlots } from "@/utils/components"
import { mergeLegacyRawStyles } from "@/patches/mergeLegacyRawStyles"

import type { StyleValue, FrappeUIComponent, FrappeUIComponents } from "@/types"
import type { ComponentEvent } from "@/types/ComponentEvent"

export type styleProperty = keyof CSSProperties | `__${string}`;

class Block implements BlockOptions {
	componentId: string
	componentName: string
	componentProps: Record<string, any>
	componentSlots: Record<string, Slot>
	componentEvents: Record<string, any>
	attributes: Record<string, any>
	blockName?: string
	children: Block[]
	parentBlock: Block | null
	baseStyles: BlockStyleMap
	mobileStyles: BlockStyleMap
	tabletStyles: BlockStyleMap
	visibilityCondition?: string
	__lastVisibilityCondition?: string | undefined
	originalElement?: string
	classes?: string[]
	parentSlotName?: string
	// studio component specific
	isStudioComponent?: boolean
	isChildOfComponent?: string
	extendedFromComponent?: Block // for the component root
	isCustomVueComponent?: boolean // custom vue component from frappe app
	// temporary properties
	slotScope?: SlotScope | null
	componentContext?: Record<string, any> | null

	// @editor-only
	private static components: FrappeUIComponents | null = null

	constructor(options: BlockOptions) {
		this.componentName = options.componentName
		this.blockName = options.blockName
		this.originalElement = options.originalElement
		this.baseStyles = reactive(mergeLegacyRawStyles({ ...(options.baseStyles || {}) }, options.rawStyles))
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

		if (options.isStudioComponent) {
			this.isStudioComponent = options.isStudioComponent
			const componentStore = useComponentStore()
			componentStore.loadComponent(this.componentName)
		}
		if (options.isCustomVueComponent) {
			this.isCustomVueComponent = options.isCustomVueComponent
			// Warm the slot cache so canHaveChildren() knows this component's default slot
			void getComponentSlots(this.componentName, true)
		}

		// get component props
		if (!options.componentProps) {
			this.componentProps = copyObject(Block.components?.[options.componentName]?.initialState)
		} else {
			this.componentProps = options.componentProps
		}
		this.attributes = reactive(options.attributes || {})

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
		Object.defineProperty(this, "slotScope", {
			value: options.slotScope || null,
			writable: true,
			enumerable: false,
			configurable: true
		})
		Object.defineProperty(this, "componentContext", {
			value: options.componentContext || null,
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

	addChild(child: BlockOptions, index?: number | null, select = true) {
		if (child.parentSlotName) {
			return this.updateSlot(child.parentSlotName, child, index)
		}

		index = this.getValidIndex(index, this.children.length)
		const childBlock = reactive(new Block(child))
		childBlock.parentBlock = this
		this.children.splice(index, 0, childBlock)
		if (select) {
			childBlock.selectBlock()
		}
		return childBlock
	}

	removeChild(child: Block) {
		const index = this.getChildIndex(child)
		if (index === -1) return

		if (child.isSlotBlock()) {
			this.getSlotContent(child.parentSlotName!)?.splice(index, 1)
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
			return this.getSlotContent(child.parentSlotName)
				?.findIndex((block) => block.componentId === child.componentId)
		}
		return this.children.findIndex((block) => block.componentId === child.componentId)
	}

	// Find a direct child by id, searching the regular children AND every named slot's content.
	getChildById(componentId: string): Block | null {
		const child = this.children.find((block) => block.componentId === componentId)
		if (child) return child
		for (const slot of Object.values(this.componentSlots)) {
			const found = slot.slotContent.find((block) => block.componentId === componentId)
			if (found) return found
		}
		return null
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
		if (
			this.isRoot() ||
			this.isContainer() ||
			this.hasComponentSlots() ||
			this.hasChildren() ||
			this.hasDefaultSlot()
		)
			return true
		return false
	}

	hasDefaultSlot() {
		return componentHasDefaultSlot(this.componentName)
	}

	isRoot() {
		return this.componentId === "root" || this.originalElement === "body";
	}

	isContainer() {
		return this.originalElement === "div" || this.originalElement === "header" || this.componentName === "FitContainer" || this.componentName === "Container";
	}

	getParentBlock(): Block | null {
		return this.parentBlock || null;
	}

	// children first to match the visual order in the Layers panel
	getChildrenAndSlotContent(): Block[] {
		const slotContent = Object.values(this.componentSlots).flatMap((slot) => slot.slotContent);
		return [...this.children, ...slotContent];
	}

	// nearest block (including self) with the given componentName
	closest(componentName: string): Block | null {
		let current: Block | null = this;
		while (current) {
			if (current.componentName === componentName) return current;
			current = current.getParentBlock();
		}
		return null;
	}

	// whether a component can mount under this block — non-standalone family parts crash outside their family root
	canAddChild(component: FrappeUIComponent): boolean {
		if (component.isStandalone === false && component.group) {
			return Boolean(this.closest(component.group));
		}
		return true;
	}

	getSiblingBlock(direction: "next" | "previous") {
		const parentBlock = this.getParentBlock();
		if (!parentBlock) return null;
		const siblings = this.parentSlotName
			? (parentBlock.getSlotContent(this.parentSlotName) as Block[])
			: parentBlock.children;
		const index = parentBlock.getChildIndex(this);
		const sibling = direction === "next" ? siblings[index + 1] : siblings[index - 1];
		return sibling || null;
	}

	getIcon() {
		switch(true) {
			case this.isRoot():
				return LucideHash
			case this.componentName === "container":
				return LucideAppWindow
			case this.isStudioComponent:
				return LucideBox
			case this.isCustomVueComponent:
				return LucideCode
			default:
				return Block.components?.[this.componentName]?.icon || LucideHash
		}
	}

	getBlockDescription() {
		if (this.isStudioComponent) {
			const componentStore = useComponentStore()
			return componentStore.getComponentName(this.componentName)
		}
		return this.blockName || this.componentName || this.originalElement
	}

	// fragment mode
	editInFragmentMode() {
		return Block.components?.[this.componentName]?.editInFragmentMode
	}

	isOverlayNode(): boolean {
		if (this.isStudioComponent) {
			const componentStore = useComponentStore()
			return Boolean(componentStore.componentMap.get(this.componentName)?.isOverlayNode())
		}
		return Boolean(this.editInFragmentMode())
	}

	hasNonOverlayContent(): boolean {
		return this.getChildrenAndSlotContent().some((child) => {
			if (child.isOverlayNode()) return false
			if (!child.isContainer()) return true
			return child.hasNonOverlayContent()
		})
	}

	findFirstOverlayNode(): Block | null {
		for (const child of this.getChildrenAndSlotContent()) {
			if (child.isOverlayNode()) return child
			const nestedOverlay = child.findFirstOverlayNode()
			if (nestedOverlay) return nestedOverlay
		}
		return null
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

	removeStyle(style: styleProperty) {
		style = kebabToCamelCase(style as string) as styleProperty
		delete this.baseStyles[style]
		delete this.tabletStyles[style]
		delete this.mobileStyles[style]
	}

	getClasses() {
		return [...this.classes || []]
	}

	addClass(className: string) {
		if (!this.classes) {
			this.classes = []
		}
		if (!this.classes.includes(className)) {
			this.classes.push(className)
		}
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

	toggleVisibilityCondition() {
		if (this.visibilityCondition) {
			this.__lastVisibilityCondition = this.visibilityCondition
			this.visibilityCondition = undefined
		} else if (this.__lastVisibilityCondition) {
			this.visibilityCondition = this.__lastVisibilityCondition
			this.__lastVisibilityCondition = undefined
		}
	}

	hasVisibilityCondition() {
		return this.visibilityCondition || this.__lastVisibilityCondition
	}

	isVisible() {
		return this.getStyle("display") !== "none"
	}

	isHTML() {
		return this.componentName === "HTML"
	}

	getHTML() {
		return this.isHTML() ? this.getProp("html") : null
	}

	setHTML(html: string) {
		if (this.isHTML()) {
			this.setProp("html", html)
		}
	}

	isText() {
		return this.componentName === "TextBlock"
	}

	isSVG() {
		return this.isHTML() && this.getProp("html")?.trim().startsWith("<svg")
	}

	isIframe() {
		return this.isHTML() && this.getProp("html")?.trim().startsWith("<iframe")
	}

	isFlex() {
		return this.getRenderedStyle("display") === "flex"
	}

	isGrid() {
		return this.getRenderedStyle("display") === "grid"
	}

	// detect actual layout type directly from rendered element if not set in block styles
	getRenderedStyle(style: styleProperty): StyleValue {
		const configuredStyle = this.getStyle(style)
		if (configuredStyle || typeof document === "undefined") return configuredStyle
		const element = this.getRenderedElement()
		if (!element) return undefined
		return (getComputedStyle(element) as unknown as Record<string, StyleValue>)[style] || undefined
	}

	getRenderedElement(): HTMLElement | null {
		const activeCanvas = useCanvasStore().activeCanvas
		const breakpoint = activeCanvas?.activeBreakpoint
		if (!breakpoint) return null
		const scope: ParentNode = activeCanvas?.canvasContainer || document
		return scope.querySelector(
			`.__studio_component__[data-component-id="${this.componentId}"][data-breakpoint="${breakpoint}"]`,
		)
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
	getProp(propName: string) {
		return this.componentProps[propName]
	}

	setProp(propName: string, value: any) {
		this.componentProps[propName] = value
	}

	removeProp(propName: string) {
		delete this.componentProps[propName]
	}

	// attributes
	getAttributes() {
		return { ...this.attributes }
	}

	setAttributes(attributes: Record<string, any>) {
		Object.keys(this.attributes).forEach((key) => {
			if (!(key in attributes)) {
				delete this.attributes[key]
			}
		})
		Object.assign(this.attributes, attributes)
	}

	getPropsAndAttributes() {
		return { ...this.componentProps, ...this.attributes }
	}

	// component slots
	initializeSlots() {
		Object.entries(this.componentSlots).forEach(([slotName, slot]) => {
			if (!slot.slotId) {
				slot.slotId = this.generateSlotId(slotName)
			}
			slot.parentBlockId = this.componentId

			slot.slotContent = (Array.isArray(slot.slotContent) ? slot.slotContent : []).map((block) => {
				block.parentBlock = this
				return reactive(new Block(block))
			})
		})
	}

	addSlot(slotName: string) {
		this.componentSlots[slotName] = {
			slotName: slotName,
			slotId: this.generateSlotId(slotName),
			slotContent: [],
			parentBlockId: this.componentId
		}
		nextTick(() => {
			const canvasStore = useCanvasStore()
			canvasStore.activeCanvas?.selectSlot(this.componentSlots[slotName])
		})
	}

	updateSlot(slotName: string, content: Block | BlockOptions, index?: number | null) {
		// for top-level blocks inside a slot
		content.parentSlotName = slotName
		content.parentBlock = this
		const slotContent = this.componentSlots[slotName].slotContent
		index = this.getValidIndex(index, slotContent.length)
		const childBlock = reactive(new Block(content))
		slotContent.splice(index, 0, childBlock)
		childBlock.selectBlock()
		return childBlock
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

	isSlotBlock() {
		return Boolean(this.parentSlotName)
	}

	// repeater
	isRepeater() {
		return this.componentName === "Repeater"
	}

	isRepeated(): boolean {
		let current = this.getParentBlock()
		while (current) {
			if (current.isRepeater()) return true
			current = current.getParentBlock()
		}
		return false
	}

	// scoped slots
	setSlotScope(slotScope: SlotScope | null) {
		// temporarily set the enclosing scoped slot props on selected block for autocompletions
		this.slotScope = slotScope
	}

	getCompletions(): CompletionSource[] {
		const completions = this.getSlotScopeCompletions()
		if (this.componentContext) {
			completions.push(
				{
					item: this.componentContext.inputs || {},
					completion: {
						label: "inputs",
						type: "data",
						detail: "Component Context",
					}
				},
			)
		}

		return completions
	}

	getSlotScopeCompletions(): CompletionSource[] {
		const detail = this.isRepeated() ? "Repeater Scope" : "Slot Scope"
		return Object.entries(this.slotScope || {}).map(([name, value]) => ({
			item: value,
			completion: {
				label: name,
				type: "data",
				detail,
			},
		}))
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

	// studio components
	extendFromComponent(componentName: string) {
		let parentBlock = this.getParentBlock()
		const newBlock = getComponentBlock(componentName, true)

		// If this is a slot block, preserve the slot information
		if (this.isSlotBlock()) {
			newBlock.parentSlotName = this.parentSlotName
		}

		parentBlock?.replaceChild(this, newBlock)
	}

	initializeStudioComponent(studioComponent: Block) {
		this.componentId = studioComponent.componentId
		this.extendedFromComponent = studioComponent

		function linkParentComponentId(block: Block, studioComponentId: string) {
			block.getChildrenAndSlotContent().forEach((child) => {
				child.isChildOfComponent = studioComponentId
				child.classes?.push("__studio_component_child__")
				linkParentComponentId(child, studioComponentId)
			})
		}
		linkParentComponentId(this, studioComponent.componentId)
	}

	setComponentContext(componentContext: Record<string, any>) {
		// temporarily set componentContext on selected block for autocompletions
		this.componentContext = componentContext
	}
}

export default Block