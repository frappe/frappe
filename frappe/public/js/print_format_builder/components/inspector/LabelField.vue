<template>
	<div class="label-field">
		<InspectorRow :label="label" :toggle="showToggle">
			<Switch
				v-if="showToggle"
				:label="showLabel"
				:model-value="show_on"
				@update:model-value="(on) => $emit('update:show', on ? 'show' : 'hide')"
			/>
			<input
				v-else
				class="form-control form-control-sm pfb-insp-input"
				type="text"
				:placeholder="placeholder"
				:value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)"
			/>
		</InspectorRow>
		<input
			v-if="showToggle && show_on"
			class="form-control form-control-sm pfb-insp-input"
			type="text"
			:placeholder="placeholder"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
	</div>
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
.label-field {
	display: flex;
	flex-direction: column;
	gap: 8px;
}
</style>
