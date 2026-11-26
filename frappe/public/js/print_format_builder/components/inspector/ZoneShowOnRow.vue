<template>
	<DropdownRow
		:label="__('Show on')"
		:model-value="layout[zone]?.show_on || ''"
		:options="options"
		@update:model-value="(value) => set_prop(layout[zone], 'show_on', value)"
	/>
</template>

<script setup>
import { inject } from "vue";
import DropdownRow from "./DropdownRow.vue";
import { set_prop } from "../../utils";

defineProps({
	zone: { type: String, required: true },
});

const { layout } = inject("$store");

const options = [
	{ value: "", label: __("As in Print Settings") },
	{ value: "every_page", label: __("Every page") },
	{ value: "first_page", label: __("First page only") },
	{ value: "last_page", label: __("Last page only") },
	{ value: "after_first_page", label: __("Every page but the first") },
];
</script>
