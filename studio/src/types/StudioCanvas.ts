import { useCanvasHistory } from "@/utils/useCanvasHistory"
import type { IndicatorGeometry } from "@/utils/dropGeometry"
import { Ref } from "vue"

export interface BreakpointConfig {
	icon: string
	device: "desktop" | "tablet" | "mobile"
	displayName: string
	width: number
	visible: boolean
}

export interface CanvasProps {
	overlayElement: HTMLElement | null
	background: string
	scale: number
	translateX: number
	translateY: number
	settingCanvas: boolean
	scaling: boolean
	panning: boolean
	breakpoints: BreakpointConfig[]
}

export type CanvasHistory = Ref<ReturnType<typeof useCanvasHistory>>

export interface ScreenRect {
	top: number
	left: number
	width: number
	height: number
}

// on-canvas block reorder feedback, read by the DropIndicator overlay
export interface ReorderTarget {
	active: boolean
	// insertion line geometry, screen px
	line: IndicatorGeometry | null
	containerRect: ScreenRect | null
	// dropping into a named slot (purple accent) vs regular children (blue)
	isSlotTarget: boolean
	// dropping into the block's own container (reorder) vs a different one
	isSameContainer: boolean
}
