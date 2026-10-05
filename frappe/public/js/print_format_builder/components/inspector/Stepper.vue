<template>
	<div class="pfb-stepper" :class="{ 'pfb-stepper--sm': sm }">
		<button
			type="button"
			class="es-button"
			data-variant="subtle"
			data-size="sm"
			data-icon-button="true"
			:aria-label="__('Decrease')"
			@click="$emit('decrement')"
			v-html="frappe.utils.icon('minus', 'sm')"
		></button>
		<span class="pfb-stepper-value">
			<input
				class="pfb-stepper-input"
				type="number"
				:min="min"
				:value="value"
				:placeholder="placeholder"
				:style="{ width: input_width }"
				@change="(e) => $emit('input', e.target.value)"
			/>
			<span v-if="unit && value !== '' && value != null" class="pfb-stepper-unit">{{
				unit
			}}</span>
		</span>
		<button
			type="button"
			class="es-button"
			data-variant="subtle"
			data-size="sm"
			data-icon-button="true"
			:aria-label="__('Increase')"
			@click="$emit('increment')"
			v-html="frappe.utils.icon('plus', 'sm')"
		></button>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	value: { type: [Number, String], default: "" },
	min: { type: [Number, String], default: 0 },
	unit: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	sm: { type: Boolean, default: false },
});
defineEmits(["decrement", "increment", "input"]);

const input_width = computed(() => {
	const shown =
		props.value === "" || props.value == null ? props.placeholder : String(props.value);
	return Math.max(shown.length, 1) + "ch";
});
</script>

<style scoped>
.pfb-stepper {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	justify-self: end;
	margin-left: auto;
}

.pfb-stepper-value {
	width: 48px;
	display: flex;
	align-items: baseline;
	justify-content: center;
	gap: 3px;
	font-size: var(--text-sm);
	color: var(--text-color);
}

.pfb-stepper-input {
	min-width: 0;
	text-align: right;
	font-size: var(--text-sm);
	font-variant-numeric: tabular-nums;
	border: none;
	background: transparent;
	color: inherit;
	padding: 0;
	outline: none;
	-moz-appearance: textfield;
}

.pfb-stepper-input::-webkit-inner-spin-button,
.pfb-stepper-input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-stepper-unit {
	color: var(--text-muted);
}
</style>
