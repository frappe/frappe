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

type Target = HTMLElement | SVGElement

function trackTarget(target: Target | Target[], host: HTMLElement, canvasProps: CanvasProps): Tracker {
	const targets = Array.isArray(target) ? target : [target];
	const boundsList = targets.map((el) => reactive(useElementBounding(el)));
	const update = () => boundsList.forEach((bounds) => bounds.update());
	const container = targets[0]?.closest(".canvas-container");
	// TODO: too much? find a better way to track changes
	updateList.push(update);
	const stopWatch = watch(canvasProps, () => nextTick(update), { deep: true })

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
		// span the union bounding box so a slot with multiple top-level blocks is fully covered
		const top = Math.min(...boundsList.map((bounds) => bounds.top))
		const left = Math.min(...boundsList.map((bounds) => bounds.left))
		const right = Math.max(...boundsList.map((bounds) => bounds.right))
		const bottom = Math.max(...boundsList.map((bounds) => bounds.bottom))
		host.style.width = numberToPx(right - left, false)
		host.style.height = numberToPx(bottom - top, false)
		host.style.top = numberToPx(top, false)
		host.style.left = numberToPx(left, false)
	});

	const cleanup = () => {
		const index = updateList.indexOf(update)
		if (index > -1) {
			updateList.splice(index, 1)
		}
		stopWatch()
		stopEffect()
	};

	return {
		update,
		cleanup,
	}
}

export default trackTarget
