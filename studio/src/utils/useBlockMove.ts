// Ported from Builder, modified later
import { nextTick } from "vue"
import type Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import setGuides from "@/utils/guidesTracker"
import { getBlockInfo, numberToPx } from "@/utils/helpers"
import type { PauseId } from "@/utils/useCanvasHistory"

const DRAG_THRESHOLD = 4 // px before a mousedown becomes a drag
const OUT_OF_FLOW_POSITIONS = ["absolute", "fixed"]

// Out-of-flow blocks have no slot to reorder into, so they move freely instead.
export function isMovable(block: Block): boolean {
	return (
		!block.isRoot() &&
		!block.isChildOfComponent &&
		OUT_OF_FLOW_POSITIONS.includes(block.getStyle("position") as string)
	)
}

// Press-and-drag an absolutely positioned block to move it: top/left follow the
// pointer (scale-aware), the left edge snaps to canvas guides, and the whole
// move lands as one history entry on release.
export function startBlockMove(event: MouseEvent, block: Block, breakpoint?: string) {
	const canvasStore = useCanvasStore()
	const dragBreakpoint =
		breakpoint || getBlockInfo(event).breakpoint || canvasStore.activeCanvas?.activeBreakpoint || "desktop"
	const target = document.querySelector(
		`.__studio_component__[data-component-id="${block.componentId}"][data-breakpoint="${dragBreakpoint}"]`,
	) as HTMLElement | null
	if (!target || !canvasStore.activeCanvas) return
	new BlockMoveSession(event, block, target).listen()
}

class BlockMoveSession {
	private canvasStore = useCanvasStore()
	private guides: ReturnType<typeof setGuides>
	private startX: number
	private startY: number
	private startLeft: number
	private startTop: number
	private started = false
	private pauseId: PauseId | null = null
	private documentCursor = ""

	constructor(
		event: MouseEvent,
		private block: Block,
		private target: HTMLElement,
	) {
		this.guides = setGuides(target, this.canvasStore.activeCanvas!.canvasProps)
		this.startX = event.clientX
		this.startY = event.clientY
		// offsetLeft/Top are layout px (unaffected by the canvas transform), the
		// same space the block's top/left styles live in
		this.startLeft = target.offsetLeft
		this.startTop = target.offsetTop
	}

	listen() {
		document.addEventListener("mousemove", this.onMove)
		document.addEventListener("mouseup", this.onUp)
	}

	private onMove = async (event: MouseEvent) => {
		if (!this.started) {
			const movedX = Math.abs(event.clientX - this.startX)
			const movedY = Math.abs(event.clientY - this.startY)
			if (movedX < DRAG_THRESHOLD && movedY < DRAG_THRESHOLD) return
			this.beginMove()
		}
		event.preventDefault()
		const scale = this.canvasStore.activeCanvas?.canvasProps.scale || 1
		const left = this.startLeft + (event.clientX - this.startX) / scale
		const top = this.startTop + (event.clientY - this.startY) / scale
		this.block.setStyle("left", numberToPx(left))
		this.block.setStyle("top", numberToPx(top))
		await nextTick()
		this.snapToGuides(left)
	}

	private snapToGuides(left: number) {
		const { leftOffset, rightOffset } = this.guides.getPositionOffset()
		const offset = leftOffset || rightOffset
		if (offset) this.block.setStyle("left", numberToPx(left + offset))
	}

	private beginMove() {
		this.started = true
		this.canvasStore.isDragging = true
		this.canvasStore.activeCanvas?.selectBlock(this.block, null)
		this.canvasStore.preventClick = true
		this.pauseId = this.canvasStore.activeCanvas?.history?.pause() || null
		this.guides.showX()
		this.documentCursor = document.body.style.cursor
		document.body.style.cursor = "grabbing"
	}

	private onUp = () => {
		document.removeEventListener("mousemove", this.onMove)
		document.removeEventListener("mouseup", this.onUp)
		if (!this.started) return
		this.guides.hideX()
		document.body.style.cursor = this.documentCursor
		this.canvasStore.isDragging = false
		// the trailing click fires synchronously after mouseup
		setTimeout(() => (this.canvasStore.preventClick = false))
		if (this.pauseId) {
			this.canvasStore.activeCanvas?.history?.resume(this.pauseId, true)
			this.pauseId = null
		}
	}
}
