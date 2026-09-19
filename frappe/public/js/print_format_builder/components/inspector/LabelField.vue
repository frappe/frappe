<template>
	<InspectorRow :label="label" stacked>
		<div class="label-field-controls">
			<Switch
				v-if="showToggle"
				:label="showLabel"
				:model-value="show_on"
				@update:model-value="(on) => $emit('update:show', on ? 'show' : 'hide')"
			/>
			<input
				v-if="!showToggle || show_on"
				class="pfb-insp-input"
				type="text"
				:placeholder="placeholder"
				:value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)"
			/>
		</div>
	</InspectorRow>
</template>

<script setup>
import { computed } from "vue";
import InspectorRow from "./InspectorRow.vue";
import Switch from "./Switch.vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, default: () => __("Label") },
	placeholder: { type: String, default: "" },
	show: { type: String, default: undefined },
	showToggle: { type: Boolean, default: false },
	showLabel: { type: String, default: () => __("Show label") },
});
defineEmits(["update:modelValue", "update:show"]);

let show_on = computed(() => props.show !== "hide");
</script>

<style scoped>
.label-field-controls {
	display: flex;
	align-items: center;
	gap: 10px;
}

.label-field-controls .pfb-insp-input {
	flex: 1;
}
</style>
