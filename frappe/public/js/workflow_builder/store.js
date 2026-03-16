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
	let taskfields = ref([]);
	let ref_history = ref(null);
	let is_submittable = ref(true);
	let task_icons = ref({});

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

		if (!taskfields.value.length) {
			await frappe.model.with_doctype("Workflow Transition Tasks");
			taskfields.value = frappe.get_meta("Workflow Transition Tasks").fields;
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
					fieldtype: df.fieldtype,
					options: df.options,
				}));
		}

		const workflow_data =
			(workflow_doc.value.workflow_data &&
				typeof workflow_doc.value.workflow_data == "string" &&
				JSON.parse(workflow_doc.value.workflow_data)) ||
			[];

		workflow.value.elements = get_workflow_elements(workflow_doc.value, workflow_data);

		// Fetch tasks for transitions that have a transition_tasks link
		for (const element of workflow.value.elements) {
			if (element.type === "action" && element.data.transition_tasks) {
				try {
					const doc_name = element.data.transition_tasks;
					await frappe.model.clear_doc("Workflow Transition Tasks", doc_name);
					const tasks_doc = await frappe.db.get_doc(
						"Workflow Transition Tasks",
						doc_name
					);
					if (tasks_doc) {
						element.data.tasks = tasks_doc.tasks
							? tasks_doc.tasks.map((t) => ({
									task: t.task,
									email_template: t.email_template,
									receiver_by_document_field: t.receiver_by_document_field,
									link: t.link,
							  }))
							: [];

						for (const t of element.data.tasks) {
							if (t.task == "Server Script" && t.link) {
								await frappe.model.clear_doc("Server Script", t.link);
								await frappe.model.with_doc("Server Script", t.link);
								let server_script_doc = frappe.get_doc("Server Script", t.link);
								t.script = server_script_doc.script;
								t.script_name = t.link;
							}
						}
					}
				} catch (e) {
					element.data.tasks = [];
				}
			} else if (element.type === "action") {
				element.data.tasks = [];
			}
		}
		await update_is_submittable();
		reset_non_submittable_states();

		setup_undo_redo();
		setup_breadcrumbs();
	}

	function reset_changes() {
		fetch();
	}

	function get_transition_tasks_data() {
		const transition_tasks_data = {};
		for (const element of workflow.value.elements) {
			if (element.type !== "action" || !element.data.action) continue;
			if (
				!(element.data.tasks && element.data.tasks.length > 0) &&
				!element.data.transition_tasks
			) {
				continue;
			}

			transition_tasks_data[element.id] = {
				transition_tasks: element.data.transition_tasks || null,
				tasks: (element.data.tasks || []).map((t) => ({
					task: t.task,
					email_template: t.email_template,
					receiver_by_document_field: t.receiver_by_document_field,
					link: t.link,
					script: t.script,
					script_name: t.script_name,
				})),
			};
		}
		return transition_tasks_data;
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

			const transition_tasks_data = get_transition_tasks_data();

			await frappe.call({
				method: "frappe.workflow.doctype.workflow.workflow.save_workflow",
				args: {
					doc: doc,
					transition_tasks_data: transition_tasks_data,
				},
			});

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
					transition_tasks: data.transition_tasks,
				};
			}

			return obj;
		});
	}

	function setup_breadcrumbs() {
		let breadcrumbs = `
			<li><a href="/desk/workflow">${__("Workflow")}</a></li>
			<li><a href="/desk/workflow/${workflow_name.value}">${__(workflow_name.value)}</a></li>
			<li class="disabled"><a href="#">${__("Workflow Builder")}</a></li>
		`;
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.$breadcrumbs.append(breadcrumbs);
	}

	async function update_is_submittable() {
		if (!workflow_doc.value?.document_type) {
			is_submittable.value = true;
			return;
		}
		await frappe.model.with_doctype(workflow_doc.value.document_type);
		is_submittable.value =
			frappe.get_meta(workflow_doc.value.document_type)?.is_submittable || false;
	}

	function reset_non_submittable_states() {
		if (is_submittable.value) return;

		let has_affected_states = false;
		workflow.value.elements.forEach((el) => {
			if (el.type === "state" && el.data.doc_status && el.data.doc_status !== "Draft") {
				has_affected_states = true;
				el.data.doc_status = "Draft";
			}
		});

		if (has_affected_states) {
			frappe.msgprint({
				title: __("Doc Status Reset"),
				message: __(
					"The <strong>Doc Status</strong> for all states has been reset to <strong>Draft</strong> because <strong>{0}</strong> is not submittable",
					[workflow_doc.value.document_type]
				),
				indicator: "orange",
			});
		}
	}

	function get_state_df(data) {
		let doc_status_map = {
			Draft: 0,
			Submitted: 1,
			Cancelled: 2,
		};
		data.doc_status = is_submittable.value ? doc_status_map[data.doc_status] : 0;
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

	async function remove_task_from_transition(p_node, task_obj) {
		let source_node = workflow.value.elements.find((el) => el.id === p_node.id);
		if (!source_node || !source_node.data) return;

		if (!source_node.data.tasks) return;

		const index = source_node.data.tasks.findIndex((t) => t.task === task_obj.task);
		if (index > -1) {
			source_node.data.tasks.splice(index, 1);
			source_node.data = { ...source_node.data };
		}
		ref_history.value.commit();
	}

	async function move_task(p_node, from_index, to_index) {
		let source_node = workflow.value.elements.find((el) => el.id === p_node.id);
		if (!source_node || !source_node.data) return;

		if (!source_node.data.tasks) return;

		if (to_index >= 0 && to_index < source_node.data.tasks.length) {
			let new_tasks = [...source_node.data.tasks];
			const task = new_tasks.splice(from_index, 1)[0];
			new_tasks.splice(to_index, 0, task);
			source_node.data.tasks = new_tasks;
			source_node.data = { ...source_node.data };
		}
		ref_history.value.commit();
	}

	async function add_task_to_transition(p_node, task_name) {
		let source_node = workflow.value.elements.find((el) => el.id === p_node.id);
		if (!source_node || !source_node.data) return;

		if (!source_node.data.tasks) source_node.data.tasks = [];

		if (!source_node.data.tasks.some((t) => t.task === task_name)) {
			source_node.data.tasks.push({
				task: task_name,
				email_template: null,
				receiver_by_document_field: null,
				link: null,
			});
			source_node.data = { ...source_node.data };
		}

		ref_history.value.commit();
	}

	async function update_task_config(p_node, task_index, updates) {
		let source_node = workflow.value.elements.find((el) => el.id === p_node.id);
		if (!source_node || !source_node.data) return;

		if (source_node.data.tasks && source_node.data.tasks[task_index]) {
			Object.assign(source_node.data.tasks[task_index], updates);
			source_node.data = { ...source_node.data };
		}
		ref_history.value.commit();
	}

	return {
		workflow_name,
		workflow_doc,
		workflow_doc_fields,
		workflow,
		workflowfields,
		statefields,
		transitionfields,
		taskfields,
		ref_history,
		task_icons,
		fetch,
		reset_changes,
		save_changes,
		setup_undo_redo,
		add_task_to_transition,
		remove_task_from_transition,
		move_task,
		update_task_config,
		is_submittable,
		update_is_submittable,
		reset_non_submittable_states,
	};
});
