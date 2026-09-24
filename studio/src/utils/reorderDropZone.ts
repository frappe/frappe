// Ported from Builder, modified later
import Block from "@/utils/block"
import { getLayoutDirection } from "@/utils/dropGeometry"
import type { FrappeUIComponent } from "@/types"

const BLOCK_SELECTOR = ".__studio_component__"
// blocks inside a studio component instance aren't editable, so the instance root is the hit target
const HIT_SELECTOR = `${BLOCK_SELECTOR}:not(.__studio_component_child__)`
// an empty named slot renders a placeholder div (slot blocks carry the class too, but are blocks)
const EMPTY_SLOT_SELECTOR = `.__studio_component_slot__:not(${BLOCK_SELECTOR})`

// Fraction of a container's main-axis extent, at EACH end, reserved for "reorder
// beside me" instead of "nest inside me". Without this you could only reorder
// past a child container by hitting the hairline gap between siblings —
// impossible when they're flush. 0.3 → the outer 30% on each side reorders, the
// inner 40% nests.
const EDGE_REORDER_BAND = 0.3
// Empty containers default to before/after (you usually want a sibling next to
// an existing block, not to drop inside it); nesting keeps a dead-centre core.
const EDGE_REORDER_BAND_EMPTY = 0.42

export interface DropZone {
	parent: Block
	slotName: string | null
	// element whose layout (direction, padding, alignment) frames the drop
	layoutEl: HTMLElement
	// rendered siblings in DOM order, the dragged block excluded
	siblingEls: HTMLElement[]
}

export function familyPlacementMessage(component: FrappeUIComponent): string {
	const familyRoot = Block.getComponents()?.[component.group as string]
	return `${component.title} can only be placed inside a ${familyRoot?.title || component.group}`
}

// Resolves where a dragged block would land from whatever is under the cursor,
// no modifier keys. Decided from the DEEPEST hovered block only (deeper climbing
// wrongly pops out of tall containers like a grid's lower row):
//  - a childless leaf → beside it, among its siblings (slot-aware)
//  - a container hovered on its inner core → nest inside it
//  - a container hovered on its outer edge band → beside it
//  - a gap between items → elementFromPoint already returns the parent
export class DropZoneResolver {
	// set when the last resolve refused a target for family reasons, so the
	// engine can explain a rejected drop
	rejectedComponent: FrappeUIComponent | null = null

	constructor(
		private dragged: Block,
		private findBlock: (id: string) => Block | null,
	) {}

	resolve(clientX: number, clientY: number): DropZone | null {
		this.rejectedComponent = null
		const element = document.elementFromPoint(clientX, clientY) as HTMLElement | null
		return this.emptySlotZone(element) || this.blockZone(element, clientX, clientY)
	}

	// dropping on an empty slot's placeholder targets that slot, not the owner's children
	private emptySlotZone(element: HTMLElement | null): DropZone | null {
		const placeholder = element?.closest(EMPTY_SLOT_SELECTOR) as HTMLElement | null
		const owner = placeholder?.dataset.componentId ? this.findBlock(placeholder.dataset.componentId) : null
		const slotName = placeholder?.dataset.slotName || null
		if (!placeholder || !owner || !slotName || this.isInsideDragged(owner)) return null
		// a component instance's placeholder carries the instance id, but the
		// slot lives on the rendered definition — the page block has no such slot
		if (owner.isStudioComponent || !owner.getSlot(slotName)) return null
		return this.zoneFor(owner, slotName, placeholder.dataset.breakpoint || "desktop", placeholder)
	}

	private blockZone(element: HTMLElement | null, clientX: number, clientY: number): DropZone | null {
		const hoveredEl = (element?.closest(HIT_SELECTOR) as HTMLElement | null) || null
		const hovered = this.hoveredBlock(hoveredEl)
		if (!hoveredEl || !hovered) return null
		const breakpoint = hoveredEl.dataset.breakpoint || "desktop"
		const beside = this.besideZone(hovered, breakpoint)
		if (this.canNestInto(hovered, beside, breakpoint, clientX, clientY)) {
			return this.zoneFor(hovered, null, breakpoint) || beside
		}
		return beside
	}

	private hoveredBlock(element: HTMLElement | null): Block | null {
		const id = element?.dataset.componentId
		let block = id ? this.findBlock(id) : null
		while (block && this.isInsideDragged(block)) block = block.getParentBlock()
		return block
	}

	private isInsideDragged(candidate: Block): boolean {
		let node: Block | null = candidate
		while (node) {
			if (node.componentId === this.dragged.componentId) return true
			node = node.getParentBlock()
		}
		return false
	}

	private besideZone(block: Block, breakpoint: string): DropZone | null {
		const parent = block.getParentBlock()
		if (!parent) return null
		return this.zoneFor(parent, block.parentSlotName || null, breakpoint)
	}

	private canNestInto(
		block: Block,
		beside: DropZone | null,
		breakpoint: string,
		clientX: number,
		clientY: number,
	): boolean {
		if (!block.canHaveChildren() || block.isStudioComponent) return false
		const others = block.children.filter((child) => child.componentId !== this.dragged.componentId)
		// Dropping back into the source's own parent as its only child is a no-op,
		// so fall through to before/after it — this is what lets a nested block be
		// dragged OUT of its parent.
		if (this.isDraggedParent(block) && !this.dragged.isSlotBlock() && others.length === 0) return false
		const blockEl = this.getBlockEl(block, breakpoint)
		if (!blockEl) return false
		if (!beside) return true
		const band = others.length === 0 ? EDGE_REORDER_BAND_EMPTY : EDGE_REORDER_BAND
		return !this.inEdgeBand(blockEl, beside.layoutEl, clientX, clientY, band)
	}

	private isDraggedParent(block: Block): boolean {
		return block.componentId === this.dragged.getParentBlock()?.componentId
	}

	// Is the pointer in the element's outer band (not its inner core), measured
	// along its container's layout axis?
	private inEdgeBand(
		element: HTMLElement,
		layoutEl: HTMLElement,
		clientX: number,
		clientY: number,
		fraction: number,
	): boolean {
		const direction = getLayoutDirection(getComputedStyle(layoutEl))
		const rect = element.getBoundingClientRect()
		const low = direction === "row" ? rect.left : rect.top
		const high = direction === "row" ? rect.right : rect.bottom
		const pointer = direction === "row" ? clientX : clientY
		const band = (high - low) * fraction
		return pointer < low + band || pointer > high - band
	}

	// `host` is where to search for the zone's elements. Renderless components (a
	// Popover) have no element of their own, so without a host the search falls
	// back to the canvas root; ids are unique, so that is safe.
	private zoneFor(
		parent: Block,
		slotName: string | null,
		breakpoint: string,
		host?: HTMLElement | null,
	): DropZone | null {
		if (!this.accepts(parent)) return null
		const scope = host || this.getBlockEl(parent, breakpoint) || this.getBlockEl(rootOf(parent), breakpoint)
		if (!scope) return null
		const blocks = slotName ? parent.getSlotContent(slotName) || [] : parent.children
		const elements = blocks
			.map((block) => this.findChildEl(scope, block, breakpoint))
			.filter((element): element is HTMLElement => Boolean(element))
		// components may render their children inside a wrapper, so measure the
		// element that actually lays them out
		const layoutEl = elements[0]?.parentElement || this.emptySlotEl(scope, parent, slotName) || scope
		// out-of-flow siblings occupy no slot, so they must not shape the geometry
		const siblingEls = elements.filter(
			(element) =>
				element.dataset.componentId !== this.dragged.componentId && hasSize(element) && inFlow(element),
		)
		return { parent, slotName, layoutEl, siblingEls }
	}

	// Non-standalone family parts (a Radio, a SettingsNavItem) crash outside
	// their family root, so they only get zones under one — as the panel drop does.
	private accepts(parent: Block): boolean {
		const component = Block.getComponents()?.[this.dragged.componentName]
		if (!component || parent.canAddChild(component)) return true
		this.rejectedComponent = component
		return false
	}

	private getBlockEl(block: Block, breakpoint: string): HTMLElement | null {
		return document.querySelector(
			`${BLOCK_SELECTOR}[data-component-id="${block.componentId}"][data-breakpoint="${breakpoint}"]`,
		)
	}

	private findChildEl(parentEl: HTMLElement, block: Block, breakpoint: string): HTMLElement | null {
		return parentEl.querySelector(
			`${BLOCK_SELECTOR}[data-component-id="${block.componentId}"][data-breakpoint="${breakpoint}"]`,
		)
	}

	private emptySlotEl(parentEl: HTMLElement, parent: Block, slotName: string | null): HTMLElement | null {
		if (!slotName) return null
		const slotId = parent.getSlot(slotName)?.slotId
		return parentEl.querySelector(`.__studio_component_slot__[data-slot-id="${slotId}"]`)
	}
}

function rootOf(block: Block): Block {
	let root = block
	while (root.getParentBlock()) root = root.getParentBlock() as Block
	return root
}

function inFlow(element: HTMLElement): boolean {
	return !["absolute", "fixed"].includes(getComputedStyle(element).position)
}

function hasSize(element: HTMLElement): boolean {
	const rect = element.getBoundingClientRect()
	return rect.width > 0 || rect.height > 0
}
