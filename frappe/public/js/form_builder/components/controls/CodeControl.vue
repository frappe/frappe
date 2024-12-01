<!-- Used as Code, HTML Editor, Markdown Editor & JSON Control -->
<script setup>
import { computed, onMounted, ref, useSlots, watch } from "vue";

const props = defineProps(["df", "read_only", "modelValue"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();

let code = ref(null);
let code_control = ref(null);
let update_control = ref(true);

let content = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

onMounted(() => {
	if (code.value) {
		code_control.value = frappe.ui.form.make_control({
			parent: code.value,
			df: {
				...props.df,
				fieldtype: "Code",
				hidden: 0,
				read_only: props.read_only,
				change: () => {
					if (update_control.value) {
						content.value = code_control.value.get_value();
					}
					update_control.value = true;
				},
			},
			value: content.value,
			disabled: Boolean(slots.label) || props.read_only,
			render_input: true,
			only_input: Boolean(slots.label),
		});
	}
});

watch(
	() => content.value,
	(value) => {
		update_control.value = false;
		code_control.value?.set_value(value ?? "");
	}
);

watch(
	() => props.df.max_height,
	(value) => {
		if (code_control.value) {
			code_control.value.ace_editor_target.css("max-height", value);
		}
	}
);
</script>

<template>
	<div v-if="slots.label" class="control" :class="{ editable: slots.label }">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div ref="code"></div>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
	<div v-else class="control" ref="code"></div>
</template>
