<script setup>
import { onMounted, ref, watch } from "vue";

const props = defineProps({
	doctype: String,
	parent_doctype: String,
	modelValue: Array, // Reactive
});

const emit = defineEmits(["update:modelValue"]);

const div = ref(null);
const filter_group = ref(null);

onMounted(() => {
	filter_group.value = new frappe.ui.FilterGroup({
		parent: $(div.value),
		doctype: props.doctype,
		parent_doctype: props.parent_doctype,
		on_change: () => {
			emit("update:modelValue", filter_group.value.get_filters());
		},
	});

	// Listen to changes of the filters prop
	watch(
		() => props.modelValue,
		(filters) => {
			filter_group.value.clear_filters();
			if (filters?.length) {
				filter_group.value.add_filters_to_filter_group(filters);
			}
		},
		{ immediate: true }
	);
});
</script>

<template>
	<div ref="div" />
</template>
