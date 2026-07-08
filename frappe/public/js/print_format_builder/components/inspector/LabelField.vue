<template>
	<div class="pfb-insp-row pfb-insp-row--col">
		<span class="pfb-insp-label">{{ label }}</span>
		<input
			class="pfb-insp-input"
			type="text"
			:placeholder="placeholder"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
	</div>
	<div class="pfb-insp-row" v-if="showToggle">
		<span class="pfb-insp-label">{{ showLabel }}</span>
		<Segmented
			:model-value="show_value"
			:options="show_options"
			@update:model-value="(v) => $emit('update:show', v)"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import Segmented from "./Segmented.vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, default: () => __("Label") },
	placeholder: { type: String, default: "" },
	show: { type: String, default: undefined },
	showToggle: { type: Boolean, default: false },
	showLabel: { type: String, default: () => __("Show label") },
});
defineEmits(["update:modelValue", "update:show"]);

let show_value = computed(() => (props.show === "hide" ? "hide" : "show"));
let show_options = [
	{ value: "show", label: __("Show") },
	{ value: "hide", label: __("Hide") },
];
</script>
