<template>
	<div ref="mount" class="pfb-colorinput"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";

// Thin wrapper around frappe's built-in Color control so the print-format
// builder reuses the standard picker (palette + native picker + hex entry)
// instead of a bespoke widget.
const props = defineProps({
	modelValue: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const mount = ref(null);
let control = null;

onMounted(() => {
	control = frappe.ui.form.make_control({
		parent: mount.value,
		df: {
			fieldtype: "Color",
			fieldname: "color",
			change: () => {
				const v = control.get_value() || "";
				if (v !== (props.modelValue || "")) emit("update:modelValue", v);
			},
		},
		render_input: true,
		only_input: true,
	});
	control.set_value(props.modelValue || "");
});

watch(
	() => props.modelValue,
	(v) => {
		if (control && (control.get_value() || "") !== (v || "")) control.set_value(v || "");
	}
);

onBeforeUnmount(() => control?.$wrapper?.remove());
</script>

<style scoped>
.pfb-colorinput :deep(.control-input) {
	min-width: 0;
}
</style>
