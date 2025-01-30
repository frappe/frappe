import { useCanvasHistory } from "@/utils/useCanvasHistory";
import { Ref } from "vue";

export interface BreakpointConfig {
	icon: string;
	device: "desktop" | "tablet" | "mobile"
	displayName: string;
	width: number;
	visible: boolean;
}

export interface CanvasProps {
	overlayElement: HTMLElement | null;
	background: string;
	scale: number;
	translateX: number;
	translateY: number;
	settingCanvas: boolean;
	scaling: boolean;
	panning: boolean;
	breakpoints: BreakpointConfig[];
}

export type CanvasHistory = Ref<ReturnType<typeof useCanvasHistory>>
