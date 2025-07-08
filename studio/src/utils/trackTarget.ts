// Extracted from Builder - modified later
import { useElementBounding, useMutationObserver } from "@vueuse/core";
import { nextTick, reactive, watch, watchEffect } from "vue";
import { numberToPx } from "./helpers";
import type { CanvasProps } from "@/types/StudioCanvas";

declare global {
	interface Window {
		observer: any;
	}
}

window.observer = null;
const updateList: (() => void)[] = [];

export interface Tracker {
	update: () => void
	cleanup: () => void
}

function trackTarget(target: HTMLElement | SVGElement, host: HTMLElement, canvasProps: CanvasProps): Tracker {
	const targetBounds = reactive(useElementBounding(target));
	const container = target.closest(".canvas-container");
	// TODO: too much? find a better way to track changes
	updateList.push(targetBounds.update);
	const stopWatch = watch(canvasProps, () => nextTick(targetBounds.update), { deep: true })

	if (!window.observer) {
		let callback = () => {
			nextTick(() => {
				updateList.forEach((fn) => {
					fn();
				});
			});
		};
		window.observer = useMutationObserver(container as HTMLElement, callback, {
			attributes: true,
			childList: true,
			subtree: true,
			attributeFilter: ["style", "class"],
			characterData: true,
		});
	}

	const stopEffect = watchEffect(() => {
		host.style.width = numberToPx(targetBounds.width, false)
		host.style.height = numberToPx(targetBounds.height, false)
		host.style.top = numberToPx(targetBounds.top, false)
		host.style.left = numberToPx(targetBounds.left, false)
	});

	const cleanup = () => {
		const index = updateList.indexOf(targetBounds.update)
		if (index > -1) {
			updateList.splice(index, 1)
		}
		stopWatch()
		stopEffect()
	};

	return {
		update: targetBounds.update,
		cleanup,
	}
}

export default trackTarget
