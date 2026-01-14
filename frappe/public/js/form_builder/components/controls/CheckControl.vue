<script setup>
import { useSlots, computed } from "vue";

const props = defineProps(["df", "value", "read_only"]);
let slots = useSlots();

// Get the display value considering both current value and default
let display_checked = computed(() => {
	// Use current value if explicitly set, otherwise fall back to default
	const value =
		props.value !== undefined && props.value !== null ? props.value : props.df.default;

	// Frappe checkboxes use "1"/"0" strings or 1/0 numbers
	return value === "1" || value === 1;
});
</script>

<template>
	<div class="control frappe-control checkbox" :class="{ editable: slots.label }">
		<!-- checkbox -->
		<label v-if="slots.label" class="field-controls">
			<div class="checkbox">
				<input type="checkbox" :checked="display_checked" disabled />
				<slot name="label" />
			</div>
			<slot name="actions" />
		</label>
		<label v-else>
			<input
				type="checkbox"
				:checked="display_checked"
				:disabled="read_only"
				@change="(event) => $emit('update:modelValue', event.target.checked ? 1 : 0)"
			/>
			<span class="label-area" :class="{ reqd: df.reqd }">{{ __(df.label) }}</span>
		</label>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="__(df.description)"></div>
	</div>
</template>

<style lang="scss" scoped>
label,
input {
	margin-bottom: 0 !important;
	cursor: pointer;
}

label .checkbox {
	display: flex;
	align-items: center;

	input {
		box-shadow: none;
		border: 1px solid var(--gray-400);
		pointer-events: none;
	}
}
</style>
