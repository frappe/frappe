<template>
	<div ref="host"></div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";

const props = defineProps({
	df: { type: Object, required: true },
	modelValue: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const host = ref(null);
let control = null;

onMounted(() => {
	control = frappe.ui.form.make_control({
		parent: host.value,
		df: { ...props.df, change: () => emit("update:modelValue", control.get_value() || "") },
		render_input: true,
		only_input: true,
	});
	control.set_value(props.modelValue || "");
});

watch(
	() => props.modelValue,
	(value) => {
		if (control && (control.get_value() || "") !== (value || ""))
			control.set_value(value || "");
	}
);
</script>

<style scoped>
:deep(.form-group) {
	margin-bottom: 0;
}
</style>
