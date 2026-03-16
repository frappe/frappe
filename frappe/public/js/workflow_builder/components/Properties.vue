<script setup>
import { ref, reactive, computed, nextTick, watch } from "vue";
import { useStore } from "../store";

let store = useStore();

let title = ref("Workflow Details");
let task_data = reactive({
	script_name: "",
	script: "",
	email_template: "",
	receiver_by_document_field: "",
});

watch(
	() => store.workflow_doc?.document_type,
	async (newDocType) => {
		if (!newDocType) return;
		await store.update_is_submittable();
		store.reset_non_submittable_states();
	}
);

// Sync local task_data when a different task is selected
watch(
	() => store.workflow.selected?.selected_task,
	(task) => {
		if (task && task.task === "Server Script") {
			task_data.script_name = task.script_name || task.link || "";
			task_data.script = task.script || "";
		} else if (task && task.task === "Email Notification") {
			task_data.email_template = task.email_template || "";
			task_data.receiver_by_document_field = task.receiver_by_document_field || "";
		}
	}
);

function onTaskPropertyChange(fieldname, value) {
	task_data[fieldname] = value;
	const selected = store.workflow.selected;
	if (selected?.selected_task && selected.selected_task_index >= 0) {
		store.update_task_config(selected, selected.selected_task_index, {
			[fieldname]: value,
		});
	}
}

let is_task_selected = computed(() => {
	const task = store.workflow.selected?.selected_task;
	return task && (task.task === "Server Script" || task.task === "Email Notification");
});

let doc = computed(() => {
	if (is_task_selected.value) {
		return task_data;
	}
	return store.workflow.selected ? store.workflow.selected.data : store.workflow_doc;
});

let properties = computed(() => {
	nextTick(() => {
		let field = $(".field input[data-fieldname!='document_type']").first();
		if (field.val() === "") field.focus();
	});

	if (store.workflow.selected && store.workflow.selected.selected_task) {
		title.value = __("Task Properties");
		let selected_task = store.workflow.selected.selected_task;

		if (selected_task && selected_task.task == "Server Script") {
			let script_fields = [
				{
					label: "Script Name",
					fieldname: "script_name",
					fieldtype: "Data",
					reqd: 1,
					description: "Name of the Server Script (API Method)",
				},
				{
					label: "Script",
					fieldname: "script",
					fieldtype: "Code",
					reqd: 1,
					enable_ace_editor: true,
				},
			];

			store.script_fields = script_fields;
			return script_fields;
		}

		if (selected_task && selected_task.task == "Email Notification") {
			const receiver_options = store.workflow_doc_fields
				.filter((f) => f.options == "Email")
				.map((f) => ({
					label: f.label,
					value: f.value,
				}));

			return [
				{
					label: "Email Template",
					fieldname: "email_template",
					fieldtype: "Link",
					options: "Email Template",
					reqd: 1,
				},
				{
					label: "Receiver By Document Field",
					fieldname: "receiver_by_document_field",
					fieldtype: "Select",
					options: receiver_options,
					reqd: 1,
				},
			];
		}
	} else if (store.workflow.selected && "action" in store.workflow.selected.data) {
		title.value = __("Transition Properties");
		return store.transitionfields.filter((df) =>
			[
				"action",
				"allowed",
				"allow_self_approval",
				"condition",
				"false_state",
				"example",
				"transition_tasks",
			].includes(df.fieldname)
		);
	} else if (store.workflow.selected && "state" in store.workflow.selected.data) {
		title.value = __("State Properties");
		let allow_edit = store.statefields.find((df) => df.fieldname == "allow_edit");
		store.statefields = store.statefields.filter(
			(df) => !["allow_edit", "workflow_builder_id"].includes(df.fieldname)
		);
		store.statefields.splice(2, 0, allow_edit);

		return store.statefields.filter((df) => {
			if (df.fieldname == "doc_status") {
				df.options = ["Draft", "Submitted", "Cancelled"];
				df.description = "";
			}
			if (df.fieldname == "update_field") {
				df.options = store.workflow_doc_fields;
			}
			return true;
		});
	}
	title.value = __("Workflow Details");
	return store.workflowfields.filter(
		(df) => !["states", "transitions", "workflow_data", "workflow_name"].includes(df.fieldname)
	);
});
</script>

<template>
	<div class="title">{{ __(title) }}</div>
	<div class="properties">
		<div class="control-data">
			<div v-if="doc">
				<div class="field" v-for="df in properties" :key="df.name">
					<component
						v-if="is_task_selected"
						:is="df.fieldtype.replaceAll(' ', '') + 'Control'"
						:df="df"
						:value="doc[df.fieldname]"
						:modelValue="doc[df.fieldname]"
						@update:modelValue="(val) => onTaskPropertyChange(df.fieldname, val)"
						:data-fieldname="df.fieldname"
						:data-fieldtype="df.fieldtype"
					/>
					<component
						v-else
						:is="df.fieldtype.replaceAll(' ', '') + 'Control'"
						:df="df"
						:value="doc[df.fieldname]"
						v-model="doc[df.fieldname]"
						:data-fieldname="df.fieldname"
						:data-fieldtype="df.fieldtype"
						:read_only="df.fieldname === 'doc_status' ? !store.is_submittable : false"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.title {
	font-size: var(--text-lg);
	font-weight: 600;
	padding: var(--padding-sm) var(--padding-md);
	border-bottom: 1px solid var(--border-color);
}
.control-data {
	height: calc(100vh - 250px);
	overflow-y: auto;
	padding: 8px;

	.field {
		margin: 5px;
		margin-top: 0;
		margin-bottom: 1rem;

		:deep(.form-control:disabled) {
			color: var(--disabled-text-color);
			background-color: var(--disabled-control-bg);
			cursor: default;
		}
		:deep(.description) {
			font-size: var(--text-sm);
			color: var(--text-muted);
		}
	}
}
</style>
