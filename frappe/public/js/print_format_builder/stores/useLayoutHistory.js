import { watch } from "vue";

export function useLayoutHistory(layoutRef, clearSelection) {
	let history = [];
	let redo_stack = [];
	let restoring = false;
	let last_snap = null;

	function take_snapshot() {
		const snap = JSON.stringify(layoutRef.value);
		if (snap === last_snap) return;
		if (last_snap !== null) history.push(last_snap);
		if (history.length > 50) history.shift();
		last_snap = snap;
		redo_stack = [];
	}

	const record_history = frappe.utils.debounce(take_snapshot, 400);

	function restore(snap) {
		restoring = true;
		last_snap = snap;
		layoutRef.value = JSON.parse(snap);
		clearSelection();
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

	function reset() {
		history = [];
		redo_stack = [];
		last_snap = JSON.stringify(layoutRef.value);
	}

	watch(
		layoutRef,
		() => {
			if (restoring) {
				restoring = false;
				return;
			}
			record_history();
		},
		{ deep: true }
	);

	return { undo, redo, reset };
}
