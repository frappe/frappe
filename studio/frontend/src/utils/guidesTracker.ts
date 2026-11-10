// Extracted from Builder
import { useElementBounding } from "@vueuse/core";
import { reactive } from "vue";
import useCanvasStore from "@/stores/canvasStore";

import type { CanvasProps } from "@/types/StudioCanvas"

const canvasStore = useCanvasStore();
const tracks = [
	{
		point: 0,
		strength: 10,
	},
	{
		point: 0.25,
		strength: 2,
	},
	{
		point: 0.5,
		strength: 10,
	},
	{
		point: 0.75,
		strength: 2,
	},
	{
		point: 1,
		strength: 10,
	},
];

function setGuides(target: HTMLElement | SVGElement, canvasProps: CanvasProps) {
	const threshold = 10;
	// TODO: Remove canvas dependency
	const canvasElement = target.closest(".canvas") as HTMLElement;
	const canvasBounds = reactive(useElementBounding(canvasElement));
	const targetBounds = reactive(useElementBounding(target));
	const parentBounds = reactive(useElementBounding(target.parentElement as HTMLElement));

	const getFinalWidth = (calculatedWidth: number) => {
		targetBounds.update();
		canvasBounds.update();
		parentBounds.update();

		const { scale } = canvasProps;
		const targetRight = targetBounds.left + calculatedWidth * scale;

		let finalWidth = calculatedWidth;
		let set = false;
		tracks.forEach((track) => {
			const canvasRight = canvasBounds.left + canvasBounds.width * track.point;
			const parentRight = parentBounds.left + parentBounds.width * track.point;
			if (Math.abs(targetRight - canvasRight) < track.strength) {
				finalWidth = (canvasRight - targetBounds.left) / scale;
				canvasStore.guides.x = canvasRight;
				set = true;
			} else if (Math.abs(targetRight - parentRight) < track.strength) {
				finalWidth = (parentRight - targetBounds.left) / scale;
				canvasStore.guides.x = parentRight;
				set = true;
			}
		});

		if (!set) {
			canvasStore.guides.x = -1;
		}

		return Math.round(finalWidth);
	};

	const getFinalHeight = (calculatedHeight: number) => {
		targetBounds.update();
		canvasBounds.update();
		parentBounds.update();

		const { scale } = canvasProps;
		const targetBottom = targetBounds.top + calculatedHeight * scale;

		let finalHeight = calculatedHeight;
		let set = false;
		tracks.forEach((track) => {
			const canvasBottom = canvasBounds.top + canvasBounds.height * track.point;
			const parentBottom = parentBounds.top + parentBounds.height * track.point;
			if (Math.abs(targetBottom - canvasBottom) < track.strength) {
				finalHeight = (canvasBottom - targetBounds.top) / scale;
				canvasStore.guides.y = canvasBottom;
				set = true;
			} else if (Math.abs(targetBottom - parentBottom) < track.strength) {
				finalHeight = (parentBottom - targetBounds.top) / scale;
				canvasStore.guides.y = parentBottom;
				set = true;
			}
		});

		if (!set) {
			canvasStore.guides.y = -1;
		}

		return Math.round(finalHeight);
	};

	const getPositionOffset = () => {
		targetBounds.update();
		canvasBounds.update();
		let { scale } = canvasProps;
		let leftOffset = 0;
		let rightOffset = 0;

		const canvasHalf = canvasBounds.left + canvasBounds.width / 2;

		if (Math.abs(targetBounds.left - canvasBounds.left) < threshold) {
			leftOffset = (canvasBounds.left - targetBounds.left) / scale;
			canvasStore.guides.x = canvasBounds.left;
		}
		if (Math.abs(targetBounds.left - canvasHalf) < threshold) {
			leftOffset = (canvasHalf - targetBounds.left) / scale;
			canvasStore.guides.x = canvasHalf;
		}
		if (Math.abs(targetBounds.left - canvasBounds.right) < threshold) {
			leftOffset = (canvasBounds.right - targetBounds.left) / scale;
			canvasStore.guides.x = canvasBounds.right;
		}

		if (Math.abs(targetBounds.right - canvasBounds.left) < threshold) {
			rightOffset = (canvasBounds.left - targetBounds.right) / scale;
			canvasStore.guides.x = canvasBounds.left;
		}
		if (Math.abs(targetBounds.right - canvasHalf) < threshold) {
			rightOffset = (canvasHalf - targetBounds.right) / scale;
			canvasStore.guides.x = canvasHalf;
		}
		if (Math.abs(targetBounds.right - canvasBounds.right) < threshold) {
			rightOffset = (canvasBounds.right - targetBounds.right) / scale;
			canvasStore.guides.x = canvasBounds.right;
		}
		if ((leftOffset && rightOffset) || (!leftOffset && !rightOffset)) {
			canvasStore.guides.x = -1;
		}
		return { leftOffset: Math.round(leftOffset), rightOffset: Math.round(rightOffset) };
	};

	const showX = () => {
		canvasStore.guides.x = -1;
		canvasStore.guides.showX = true;
	};
	const showY = () => {
		canvasStore.guides.y = -1;
		canvasStore.guides.showY = true;
	};
	const hideX = () => {
		canvasStore.guides.showX = false;
	};
	const hideY = () => {
		canvasStore.guides.showY = false;
	};

	return {
		getFinalWidth,
		getFinalHeight,
		showX,
		showY,
		hideX,
		hideY,
		getPositionOffset,
	};
}

export default setGuides;
