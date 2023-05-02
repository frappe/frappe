import { defineStore } from "pinia";
import { ref } from "vue";
import { useManualRefHistory, onKeyDown } from "@vueuse/core";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow = ref({
		elements: [
			{ id: "1", label: "Open", type: "state", position: { x: 300, y: 150 } },
			{ id: "2", label: "Approved", type: "state", position: { x: 700, y: 150 } },
			{ id: "action-1", label: "Approve", type: "action", position: { x: 500, y: 170 } },
			{
				id: "edge-1-action-1",
				source: "1",
				target: "action-1",
				type: "transition",
				sourceHandle: "right",
				targetHandle: "left",
				updatable: true,
				animated: true,
			},
			{
				id: "edge-action-1-2",
				source: "action-1",
				target: "2",
				type: "transition",
				sourceHandle: "right",
				targetHandle: "left",
				updatable: true,
				animated: true,
			},
		],
	});
	let ref_history = ref(null);

	let undo_redo_keyboard_event = onKeyDown(true, (e) => {
		if (!ref_history.value) return;
		if (e.ctrlKey || e.metaKey) {
			if (e.key === "z" && !e.shiftKey && ref_history.value.canUndo) {
				ref_history.value.undo();
			} else if (e.key === "z" && e.shiftKey && ref_history.value.canRedo) {
				ref_history.value.redo();
			}
		}
	});

	function setup_undo_redo() {
		ref_history.value = useManualRefHistory(workflow, { clone: true });

		undo_redo_keyboard_event;
	}

	return {
		workflow,
		ref_history,
		setup_undo_redo,
	};
});
