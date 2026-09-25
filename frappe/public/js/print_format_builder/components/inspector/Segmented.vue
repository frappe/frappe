<template>
	<div ref="host" class="pfb-seg"></div>
</template>

<script setup>
import { watch } from "vue";
import { useDeskWidget } from "../../composables/useDeskWidget";

const props = defineProps({
	modelValue: { type: [String, Number, Boolean], default: undefined },
	options: { type: Array, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const { host, widget } = useDeskWidget(
	(el) =>
		frappe.ui
			.tab_buttons({
				options: props.options,
				value: props.modelValue,
				size: "sm",
				on_change: (value) => emit("update:modelValue", value),
			})
			.appendTo(el)
			.data("es-tab-buttons"),
	[() => props.options]
);

watch(
	() => props.modelValue,
	(value) => {
		const group = widget.value;
		if (group && group.get_value() !== value) group.set_value(value, { silent: true });
	}
);
</script>

<style scoped>
.pfb-seg :deep(.es-tab-buttons) {
	width: 100%;
}

.pfb-seg :deep(.es-pill) {
	flex: 1;
}
</style>
