import { defineStore } from "pinia";
import { ref } from "vue";
import { get_workflow_elements } from "./utils";
import { useManualRefHistory, onKeyDown } from "@vueuse/core";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow_name = ref(null);
	let workflow_doc = ref(null);
	let workflow = ref({
		elements: [],
	});
	let ref_history = ref(null);

	async function fetch() {
		await frappe.model.clear_doc("Workflow", workflow_name.value);
		await frappe.model.with_doc("Workflow", workflow_name.value);

		workflow_doc.value = frappe.get_doc("Workflow", workflow_name.value);
		await frappe.model.with_doctype(workflow_doc.value.document_type);

		workflow.value.elements = get_workflow_elements(workflow_doc.value);

		setup_undo_redo();
	}

	function reset_changes() {
		fetch();
	}

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
		workflow_name,
		workflow,
		ref_history,
		fetch,
		reset_changes,
		setup_undo_redo,
	};
});
