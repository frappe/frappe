import {
	draggable,
	dropTargetForElements,
	monitorForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { disableNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/disable-native-drag-preview";

// auto-scroll while dragging is done in KanbanCore; the pragmatic auto-scroll package isn't installed

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
		// KanbanCore draws its own drag preview
		onGenerateDragPreview: ({ nativeSetDragImage }) =>
			disableNativeDragPreview({ nativeSetDragImage }),
		onDragStart: ({ location }) =>
			hooks.onStart &&
			hooks.onStart((location && location.current && location.current.input) || null),
		onDrop: () => hooks.onEnd && hooks.onEnd(),
	});
}

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
	});
}

// swimlanes pass canDrop so a card cannot land in another lane
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
