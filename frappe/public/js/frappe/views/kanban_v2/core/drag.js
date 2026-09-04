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
import { disableNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/disable-native-drag-preview";

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
		// Suppress the browser's flat (and, on macOS, translucent) drag image —
		// KanbanCore renders its own tilted card that follows the pointer instead.
		onGenerateDragPreview: ({ nativeSetDragImage }) =>
			disableNativeDragPreview({ nativeSetDragImage }),
		onDragStart: ({ location }) =>
			hooks.onStart &&
			hooks.onStart((location && location.current && location.current.input) || null),
		onDrop: () => hooks.onEnd && hooks.onEnd(),
	});
}

/**
 * @param {object} [hooks]
 * @param {(args: { source: object }) => boolean} [hooks.canDrop]
 *        When set, foreign boards (e.g. other swimlanes) reject the drag so
 *        drop indicators and drop handling stay within one board instance.
 */
export function bindCardDropTarget(el, getData, hooks) {
	return dropTargetForElements({
		element: el,
		getData: () => ({ ...getData() }),
		canDrop: hooks && hooks.canDrop ? hooks.canDrop : undefined,
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

/**
 * @param {(args: { source: object }) => boolean} [canDrop]
 *        Same-board gate used by swimlanes so a card cannot land in another group.
 */
export function bindColumnDropTarget(el, data, canDrop) {
	return dropTargetForElements({
		element: el,
		getData: () => ({ ...data }),
		canDrop: canDrop || undefined,
	});
}

export function startDragMonitor(onDrop) {
	return monitorForElements({ onDrop });
}
