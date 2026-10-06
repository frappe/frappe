import { ref, watch } from "vue";

export function useLayoutHistory(layoutRef, clearSelection) {
	let history = [];
	let redo_stack = [];
	let restoring = false;
	let paused = false;
	let last_snap = null;
	const can_undo = ref(false);
	const can_redo = ref(false);

	function sync() {
		can_undo.value = history.length > 0;
		can_redo.value = redo_stack.length > 0;
	}

	function take_snapshot() {
		const snap = JSON.stringify(layoutRef.value);
		if (snap === last_snap) return;
		if (last_snap !== null) history.push(last_snap);
		if (history.length > 50) history.shift();
		last_snap = snap;
		redo_stack = [];
		sync();
	}

	const record_history = frappe.utils.debounce(take_snapshot, 400);

	function restore(snap) {
		restoring = true;
		last_snap = snap;
		layoutRef.value = JSON.parse(snap);
		clearSelection();
		sync();
	}

	function undo() {
		record_history.cancel();
		take_snapshot();
		if (!history.length) return;
		redo_stack.push(last_snap);
		restore(history.pop());
	}

	function redo() {
		record_history.cancel();
		take_snapshot();
		if (!redo_stack.length) return;
		history.push(last_snap);
		restore(redo_stack.pop());
	}

	function pause(value) {
		paused = value;
		if (!value) last_snap = JSON.stringify(layoutRef.value);
	}

	function reset() {
		history = [];
		redo_stack = [];
		last_snap = JSON.stringify(layoutRef.value);
		sync();
	}

	watch(
		layoutRef,
		() => {
			if (restoring || paused) {
				restoring = false;
				return;
			}
			record_history();
		},
		{ deep: true }
	);

	return { undo, redo, reset, pause, can_undo, can_redo };
}
