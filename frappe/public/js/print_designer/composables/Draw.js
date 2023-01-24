import { useMainStore } from "../store/MainStore";
import { addEventListener, removeEventListener } from "./EventListener";
export function useDraw() {
	const MainStore = useMainStore();
	const parameters = {
		startX: 0,
		startY: 0,
		width: 0,
		height: 0,
		isMouseDown: false,
		isReversedX: false,
		isReversedY: false,
		initialScrollX: 0,
		scrollX: 0,
		initialScrollY: 0,
		scrollY: 0,
	};
	const handleScroll = (e) => {
		parameters.scrollX = canvas.parentElement.scrollLeft - parameters.initialScrollX;
		parameters.scrollY = canvas.parentElement.scrollTop - parameters.initialScrollY;
	};
	const drawEventHandler = {
		mousedown: (e) => {
			parameters.isMouseDown = true;
			parameters.width = 0;
			parameters.height = 0;
			parameters.initialX = e.clientX;
			parameters.initialY = e.clientY;
			parameters.offsetX = e.clientX - e.startX || 0;
			parameters.offsetY = e.clientY - e.startY || 0;
			parameters.startX = e.startX || e.clientX;
			parameters.startY = e.startY || e.clientY;
			parameters.initialScrollX = canvas.parentElement.scrollLeft;
			parameters.initialScrollY = canvas.parentElement.scrollTop;
			parameters.scrollX = 0;
			parameters.scrollY = 0;
			addEventListener(canvas.parentElement, "scroll", handleScroll);
		},
		mousemove: (e) => {
			let moveX = e.clientX - parameters.initialX + parameters.scrollX;
			let moveY = e.clientY - parameters.initialY + parameters.scrollY;
			let moveAbsX = Math.abs(moveX);
			let moveAbsY = Math.abs(moveY);

			if (!parameters.isMouseDown) return;

			if (moveX < 0) {
				parameters.isReversedX = true;
				parameters.startX = e.clientX - parameters.offsetX + parameters.scrollX;
				parameters.width = moveAbsX;
			} else {
				parameters.isReversedX = false;
				parameters.startX = parameters.initialX - parameters.offsetX;
				parameters.width = moveAbsX;
			}
			if (moveY < 0) {
				parameters.isReversedY = true;
				parameters.startY = e.clientY - parameters.offsetY + parameters.scrollY;
				parameters.height = moveAbsY;
			} else {
				parameters.isReversedY = false;
				parameters.startY = parameters.initialY - parameters.offsetY;
				parameters.height = moveAbsY;
			}
			if (!e.shiftKey || MainStore.isMarqueeActive) return;
			if (parameters.isReversedX) {
				parameters.startX -=
					parameters.width < parameters.height
						? parameters.height - parameters.width
						: 0;
			}
			if (parameters.isReversedY) {
				parameters.startY -=
					parameters.height < parameters.width
						? parameters.width - parameters.height
						: 0;
			}
			parameters.width = parameters.height =
				parameters.width > parameters.height ? parameters.width : parameters.height;
		},
		mouseup: (e) => {
			parameters.isMouseDown = false;
			removeEventListener(canvas.parentElement, "scroll", handleScroll);
		},
	};
	return { parameters, drawEventHandler };
}
