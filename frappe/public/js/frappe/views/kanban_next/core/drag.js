/**
 * Drag orchestration on Atlassian Pragmatic Drag and Drop (framework-agnostic).
 * Thin binding wrappers + pure geometry/array helpers; the move logic lives in
 * KanbanCore.
 */
import {
	draggable,
	dropTargetForElements,
	monitorForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter";

// NOTE: auto-scroll-while-dragging is hand-rolled in KanbanCore (the separate
// pragmatic auto-scroll package isn't installed).

/** Which half of a card the pointer is over — decides insert-before/after. */
export function closestEdge(rect, clientY) {
	return clientY < rect.top + rect.height / 2 ? "top" : "bottom";
}

export function clamp(value, min, max) {
	return Math.max(min, Math.min(max, value));
}

export function bindCardDrag(el, data, hooks) {
	return draggable({
		element: el,
		getInitialData: () => ({ ...data }),
		onDragStart: () => hooks.onStart && hooks.onStart(),
		onDrop: () => hooks.onEnd && hooks.onEnd(),
	});
}

export function bindCardDropTarget(el, getData, hooks) {
	return dropTargetForElements({
		element: el,
		getData: () => ({ ...getData() }),
		onDrag: (args) => {
			if (!hooks || !hooks.onEdge) return;
			const y =
				(args &&
					args.location &&
					args.location.current &&
					args.location.current.input &&
					args.location.current.input.clientY) ||
				0;
			hooks.onEdge(closestEdge(el.getBoundingClientRect(), y));
		},
		onDragLeave: () => hooks && hooks.onLeave && hooks.onLeave(),
		onDrop: () => hooks && hooks.onLeave && hooks.onLeave(),
	});
}

export function bindColumnDropTarget(el, data) {
	return dropTargetForElements({ element: el, getData: () => ({ ...data }) });
}

export function startDragMonitor(onDrop) {
	return monitorForElements({ onDrop });
}
