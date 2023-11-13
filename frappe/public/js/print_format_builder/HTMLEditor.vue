<template>
	<div class="html-editor">
		<div class="d-flex justify-content-end">
			<button class="btn btn-default btn-xs btn-edit" @click="toggle_edit">
				{{ !editing ? buttonLabel : __("Done") }}
			</button>
		</div>
		<div v-if="!editing" v-html="value"></div>
		<div v-show="editing" ref="editor"></div>
	</div>
</template>

<script setup>
import { ref } from "vue";

// props
const props = defineProps(["value", "button-label"]);

// emits
let emit = defineEmits(["change"]);

// variables
let editing = ref(false);
let control = ref(null);
let editor = ref(null);

// methods
function toggle_edit() {
	if (editing.value) {
		emit("change", get_value());
		editing.value = false;
		return;
	}

	editing.value = true;
	if (!control.value) {
		control.value = frappe.ui.form.make_control({
			parent: editor.value,
			df: {
				fieldname: "editor",
				fieldtype: "HTML Editor",
				min_lines: 10,
				max_lines: 30,
				change: () => {
					emit("change", get_value());
				},
			},
			render_input: true,
		});
	}
	control.value.set_value(props.value);
}
function get_value() {
	return frappe.dom.remove_script_and_style(control.value.get_value());
}
</script>

<style scoped>
.html-editor {
	position: relative;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
}

.html-editor:last-child {
	margin-bottom: 0;
}
</style>
