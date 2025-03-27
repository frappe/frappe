import { defineStore } from "pinia";
import { ref } from "vue";
import { get_workflow_elements, validate_transitions } from "./utils";
import { useManualRefHistory, onKeyDown } from "@vueuse/core";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow_name = ref(null);
	let workflow_doc = ref(null);
	let workflow_doc_fields = ref([]);
	let workflow = ref({ elements: [], selected: null });
	let workflowfields = ref([]);
	let statefields = ref([]);
	let transitionfields = ref([]);
	let ref_history = ref(null);

	async function fetch() {
		await frappe.model.clear_doc("Workflow", workflow_name.value);
		await frappe.model.with_doc("Workflow", workflow_name.value);

		workflow_doc.value = frappe.get_doc("Workflow", workflow_name.value);
		await frappe.model.with_doctype(workflow_doc.value.document_type);

		if (!workflowfields.value.length) {
			await frappe.model.with_doctype("Workflow");
			workflowfields.value = frappe.get_meta("Workflow").fields;
		}

		if (!statefields.value.length) {
			await frappe.model.with_doctype("Workflow Document State");
			statefields.value = frappe.get_meta("Workflow Document State").fields;
		}

		if (!transitionfields.value.length) {
			await frappe.model.with_doctype("Workflow Transition");
			transitionfields.value = frappe.get_meta("Workflow Transition").fields;
		}

		if (!workflow_doc_fields.value.length) {
			let doc_type = workflow_doc.value.document_type;
			await frappe.model.with_doctype(doc_type);
			workflow_doc_fields.value = frappe.meta
				.get_docfields(doc_type, null, {
					fieldtype: ["not in", frappe.model.no_value_type],
				})
				.sort((a, b) => {
					if (a.label && b.label) {
						return a.label.localeCompare(b.label);
					}
				})
				.map((df) => ({
					label: `${df.label || __("No Label")} (${df.fieldtype})`,
					value: df.fieldname,
				}));
		}

		const workflow_data =
			(workflow_doc.value.workflow_data &&
				typeof workflow_doc.value.workflow_data == "string" &&
				JSON.parse(workflow_doc.value.workflow_data)) ||
			[];

		workflow.value.elements = get_workflow_elements(workflow_doc.value, workflow_data);

		setup_undo_redo();
		setup_breadcrumbs();
	}

	function reset_changes() {
		fetch();
	}

	async function save_changes() {
		frappe.dom.freeze(__("Saving..."));

		try {
			let doc = workflow_doc.value;
			doc.states = get_updated_states();
			doc.transitions = get_updated_transitions();
			validate_workflow(doc);
			const workflow_data = clean_workflow_data();
			doc.workflow_data = JSON.stringify(workflow_data);
			await frappe.call("frappe.client.save", { doc });
			frappe.toast(__("Workflow updated successfully"));
			fetch();
		} catch (e) {
			console.error(e);
		} finally {
			frappe.dom.unfreeze();
		}
	}

	function validate_workflow(doc) {
		if (doc.is_active && (!doc.states.length || !doc.transitions.length)) {
			let message = "Workflow must have atleast one state and transition";
			frappe.throw({
				message: __(message),
				title: __("Missing Values Required"),
				indicator: "orange",
			});
		}
	}

	function clean_workflow_data() {
		return workflow.value.elements.map((el) => {
			const {
				selected,
				dragging,
				resizing,
				data,
				events,
				initialized,
				sourceNode,
				targetNode,
				...obj
			} = el;

			if (el.type == "action") {
				obj.data = {
					from_id: data.from_id,
					to_id: data.to_id,
				};
			}

			return obj;
		});
	}

	function setup_breadcrumbs() {
		let breadcrumbs = `
			<li><a href="/app/workflow">${__("Workflow")}</a></li>
			<li><a href="/app/workflow/${workflow_name.value}">${__(workflow_name.value)}</a></li>
			<li class="disabled"><a href="#">${__("Workflow Builder")}</a></li>
		`;
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.$breadcrumbs.append(breadcrumbs);
	}

	function get_state_df(data) {
		let doc_status_map = {
			Draft: 0,
			Submitted: 1,
			Cancelled: 2,
		};
		data.doc_status = doc_status_map[data.doc_status];
		return data;
	}

	function get_updated_states() {
		let states = [];
		workflow.value.elements.forEach((element) => {
			if (element.type == "state") {
				element.data.workflow_builder_id = element.id;
				states.push(get_state_df(element.data));
			}
		});
		return states;
	}

	function get_transition_df(data) {
		return data;
	}

	function get_updated_transitions() {
		let transitions = [];
		let actions = [];

		workflow.value.elements.forEach((element) => {
			if (element.type == "action") {
				element.data.workflow_builder_id = element.id;
				actions.push(element);
			}
		});

		actions.forEach((action) => {
			let states = workflow.value.elements.filter((e) => e.type == "state");

			let state = states.find(
				(state) => state.data.workflow_builder_id == action.data.from_id
			);
			let next_state = states.find(
				(state) => state.data.workflow_builder_id == action.data.to_id
			);

			if (action.data.to.length === 0 && next_state != undefined) {
				action.data.to = next_state.data.state;
			}

			let error = validate_transitions(state.data, next_state.data);
			if (error) {
				frappe.throw({
					message: error,
					title: __("Invalid Transition"),
				});
			}
			transitions.push(
				get_transition_df({
					...action.data,
					state: action.data.from,
					next_state: action.data.to,
				})
			);
		});

		return transitions;
	}

	let undo_redo_keyboard_event = () =>
		onKeyDown(true, (e) => {
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
		undo_redo_keyboard_event();
	}

	return {
		workflow_name,
		workflow_doc,
		workflow_doc_fields,
		workflow,
		workflowfields,
		statefields,
		transitionfields,
		ref_history,
		fetch,
		reset_changes,
		save_changes,
		setup_undo_redo,
	};
});
