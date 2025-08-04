<script setup>
import { useSlots } from "vue";

const props = defineProps(["df", "value", "read_only"]);
let slots = useSlots();
</script>

<template>
	<div class="control frappe-control checkbox" :class="{ editable: slots.label }">
		<!-- checkbox -->
		<label v-if="slots.label" class="field-controls">
			<div class="checkbox">
				<input type="checkbox" disabled />
				<slot name="label" />
			</div>
			<slot name="actions" />
		</label>
		<label v-else>
			<input
				type="checkbox"
				:checked="value"
				:disabled="read_only"
				@change="(event) => $emit('update:modelValue', event.target.checked)"
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
		background-color: var(--fg-color);
		box-shadow: none;
		border: 1px solid var(--gray-400);
		pointer-events: none;
	}
}
</style>
