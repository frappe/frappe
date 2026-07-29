import { reactive } from "vue";

const state = reactive({ visible: false, x: 0, y: 0, items: [] });

export function useContextMenu() {
	function open(event, items) {
		event.preventDefault();
		event.stopPropagation();
		state.items = items.filter(Boolean);
		if (!state.items.length) return;
		state.x = event.clientX;
		state.y = event.clientY;
		state.visible = true;
	}
	function close() {
		state.visible = false;
		state.items = [];
	}
	return { state, open, close };
}
