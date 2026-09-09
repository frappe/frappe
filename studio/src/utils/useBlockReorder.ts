// Ported from Builder, modified later
import type Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { getBlockInfo } from "@/utils/helpers"
import {
	clusterLines,
	collectChildRects,
	computeDropIndicator,
	computeReadingOrderIndex,
	getLayoutDirection,
	type ChildRect,
	type LayoutDirection,
} from "@/utils/dropGeometry"
import { DropZoneResolver, type DropZone } from "@/utils/reorderDropZone"
import type { PauseId } from "@/utils/useCanvasHistory"

const DRAG_THRESHOLD = 4 // px before a mousedown becomes a drag
const GHOST_OPACITY = 0.9
const OUT_OF_FLOW_POSITIONS = ["absolute", "fixed"]

// Out-of-flow blocks have no slot to reorder into; component-owned blocks are locked.
export function isReorderable(block: Block): boolean {
	return (
		!block.isRoot() &&
		!block.isChildOfComponent &&
		!OUT_OF_FLOW_POSITIONS.includes(block.getStyle("position") as string) &&
		Boolean(block.getParentBlock())
	)
}

// Pointer-based on-canvas reorder with zero layout jitter: the canvas DOM is
// never mutated during the drag. On pickup the source is hidden in place and a
// floating ghost follows the cursor; each move only measures the target's
// siblings (read-only) and repositions a fixed overlay line. The tree is
// mutated once, on release, as a single history entry.
export function startBlockReorder(event: MouseEvent, block: Block, breakpoint?: string) {
	const canvasStore = useCanvasStore()
	// the same block renders once per visible breakpoint, so measure the one the
	// drag actually happens in
	const dragBreakpoint =
		breakpoint || getBlockInfo(event).breakpoint || canvasStore.activeCanvas?.activeBreakpoint || "desktop"
	const sourceEl = document.querySelector(
		`.__studio_component__[data-component-id="${block.componentId}"][data-breakpoint="${dragBreakpoint}"]`,
	) as HTMLElement | null
	if (!sourceEl) return
	new BlockReorderSession(event, block, sourceEl).listen()
}

class BlockReorderSession {
	private canvasStore = useCanvasStore()
	private resolver: DropZoneResolver
	private sourceRect: DOMRect
	private startX: number
	private startY: number
	private grabOffsetX: number
	private grabOffsetY: number
	private started = false
	private ghost: HTMLElement | null = null
	private pauseId: PauseId | null = null
	private previousVisibility = ""
	private dropZone: DropZone | null = null
	private dropIndex: number | null = null

	constructor(
		event: MouseEvent,
		private block: Block,
		private sourceEl: HTMLElement,
	) {
		this.resolver = new DropZoneResolver(block, (id) => this.canvasStore.activeCanvas?.findBlock(id) || null)
		this.sourceRect = sourceEl.getBoundingClientRect()
		this.startX = event.clientX
		this.startY = event.clientY
		this.grabOffsetX = event.clientX - this.sourceRect.left
		this.grabOffsetY = event.clientY - this.sourceRect.top
	}

	listen() {
		document.addEventListener("mousemove", this.onMove)
		document.addEventListener("mouseup", this.onUp)
		document.addEventListener("keydown", this.onKey)
	}

	private onMove = (event: MouseEvent) => {
		if (!this.started) {
			const movedX = Math.abs(event.clientX - this.startX)
			const movedY = Math.abs(event.clientY - this.startY)
			if (movedX < DRAG_THRESHOLD && movedY < DRAG_THRESHOLD) return
			this.beginDrag()
		}
		event.preventDefault()
		this.positionGhost(event.clientX, event.clientY)
		this.updateTarget(event.clientX, event.clientY)
	}

	private onUp = () => {
		if (this.started && this.dropZone && this.dropIndex !== null) {
			this.commit(this.dropZone, this.dropIndex)
		}
		this.cleanup()
	}

	private onKey = (event: KeyboardEvent) => {
		if (event.key !== "Escape") return
		this.dropZone = null
		this.cleanup()
	}

	private beginDrag() {
		this.started = true
		this.canvasStore.isDragging = true
		// selecting on grab means point-drag doubles as selection; preventClick
		// stops the trailing click from re-selecting whatever is under the pointer
		this.canvasStore.activeCanvas?.selectBlock(this.block, null)
		this.canvasStore.preventClick = true
		this.pauseId = this.canvasStore.activeCanvas?.history?.pause() || null
		this.ghost = this.createGhost()
		document.body.appendChild(this.ghost)
		// visibility (not display) keeps the source's slot so nothing shifts on
		// pickup — critical for grids — and elementFromPoint skips it
		this.previousVisibility = this.sourceEl.style.visibility
		this.sourceEl.style.visibility = "hidden"
	}

	private createGhost(): HTMLElement {
		const scale = this.getScale()
		const ghost = document.createElement("div")
		ghost.id = "reorder-ghost"
		const clone = this.sourceEl.cloneNode(true) as HTMLElement
		clone.style.margin = "0"
		ghost.appendChild(clone)
		Object.assign(ghost.style, {
			position: "fixed",
			left: "0",
			top: "0",
			width: `${this.sourceRect.width / scale}px`,
			height: `${this.sourceRect.height / scale}px`,
			transformOrigin: "top left",
			transform: `translate(${this.sourceRect.left}px, ${this.sourceRect.top}px) scale(${scale})`,
			opacity: String(GHOST_OPACITY),
			pointerEvents: "none",
			zIndex: "999999",
			boxShadow: "0 12px 32px rgba(0,0,0,0.24), 0 2px 6px rgba(0,0,0,0.12)",
			borderRadius: "6px",
			overflow: "hidden",
			willChange: "transform",
		})
		return ghost
	}

	private positionGhost(clientX: number, clientY: number) {
		if (!this.ghost) return
		const x = clientX - this.grabOffsetX
		const y = clientY - this.grabOffsetY
		this.ghost.style.transform = `translate(${x}px, ${y}px) scale(${this.getScale()})`
	}

	private getScale(): number {
		return this.canvasStore.activeCanvas?.canvasProps?.scale || 1
	}

	private updateTarget(clientX: number, clientY: number) {
		const zone = this.resolver.resolve(clientX, clientY)
		if (!zone) return this.clearTarget()
		const style = getComputedStyle(zone.layoutEl)
		const direction = getLayoutDirection(style)
		const lines = clusterLines(collectChildRects(zone.siblingEls, direction))
		const pointerMain = direction === "row" ? clientX : clientY
		const pointerCross = direction === "row" ? clientY : clientX
		const slot = computeReadingOrderIndex(lines, pointerMain, pointerCross)
		this.dropZone = zone
		this.dropIndex = this.toBlockIndex(zone, lines.flat()[slot])
		this.showIndicator(zone, lines, slot, style, direction)
	}

	// Map the reading-order slot back to a position among the zone's non-dragged
	// blocks, so hidden or unrendered siblings can't skew the insertion index.
	private toBlockIndex(zone: DropZone, next?: ChildRect): number {
		const siblings = this.siblingBlocks(zone)
		if (!next) return siblings.length
		const nextId = zone.siblingEls[next.index].dataset.componentId
		const index = siblings.findIndex((block) => block.componentId === nextId)
		return index === -1 ? siblings.length : index
	}

	private siblingBlocks(zone: DropZone): Block[] {
		const list = zone.slotName ? zone.parent.getSlotContent(zone.slotName) || [] : zone.parent.children
		return list.filter((block) => block.componentId !== this.block.componentId)
	}

	private showIndicator(
		zone: DropZone,
		lines: ChildRect[][],
		slot: number,
		style: CSSStyleDeclaration,
		direction: LayoutDirection,
	) {
		const rect = zone.layoutEl.getBoundingClientRect()
		const target = this.canvasStore.reorderTarget
		target.active = true
		target.isSlotTarget = Boolean(zone.slotName)
		target.isSameContainer = this.isSourceZone(zone)
		target.containerRect = { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
		target.line = computeDropIndicator(lines, slot, rect, style, direction, {
			width: this.sourceRect.width,
			height: this.sourceRect.height,
		})
	}

	private isSourceZone(zone: DropZone): boolean {
		return (
			zone.parent.componentId === this.block.getParentBlock()?.componentId &&
			zone.slotName === (this.block.parentSlotName || null)
		)
	}

	private clearTarget() {
		this.dropZone = null
		this.dropIndex = null
		this.canvasStore.clearReorderTarget()
	}

	private commit(zone: DropZone, index: number) {
		const oldParent = this.block.getParentBlock()
		if (!oldParent) return
		if (this.isSourceZone(zone)) {
			oldParent.moveChild(this.block, index)
		} else {
			oldParent.removeChild(this.block)
			zone.parent.insertChild(this.block, index, zone.slotName)
		}
	}

	private cleanup() {
		document.removeEventListener("mousemove", this.onMove)
		document.removeEventListener("mouseup", this.onUp)
		document.removeEventListener("keydown", this.onKey)
		this.ghost?.remove()
		this.ghost = null
		if (this.started) {
			this.sourceEl.style.visibility = this.previousVisibility
			this.canvasStore.isDragging = false
			// the trailing click fires synchronously after mouseup, so this
			// releases the guard right after it
			setTimeout(() => (this.canvasStore.preventClick = false))
		}
		this.canvasStore.clearReorderTarget()
		if (this.pauseId) {
			// Resume WITHOUT committing: commit()'s tree mutation happens in this
			// same tick, so its deep-watch flush is still pending and the natural
			// watcher records exactly one history entry once unpaused. A no-op
			// drag leaves the tree unchanged, so nothing is recorded.
			this.canvasStore.activeCanvas?.history?.resume(this.pauseId, false)
			this.pauseId = null
		}
	}
}
