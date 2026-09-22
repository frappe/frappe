<template>
	<div ref="host" class="pfb-seg"></div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps({
	modelValue: { type: [String, Number, Boolean], default: undefined },
	options: { type: Array, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const host = ref(null);
let group = null;

function render() {
	host.value.replaceChildren();
	const $el = frappe.ui.tab_buttons({
		options: props.options,
		value: props.modelValue,
		size: "sm",
		on_change: (value) => emit("update:modelValue", value),
	});
	group = $el.data("es-tab-buttons");
	$el.appendTo(host.value);
}

onMounted(render);
onUnmounted(() => host.value?.replaceChildren());

watch(() => props.options, render, { deep: true });
watch(
	() => props.modelValue,
	(value) => {
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
