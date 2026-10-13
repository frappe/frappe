<template>
	<InspectorRow :label="label">
		<div class="pfb-insp-color">
			<ColorInput
				:model-value="modelValue"
				:placeholder="placeholder"
				@update:model-value="(v) => $emit('update:modelValue', v)"
			/>
			<slot />
		</div>
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";
import ColorInput from "./ColorInput.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.pfb-insp-color {
	display: flex;
	align-items: center;
	gap: 4px;
}
</style>
