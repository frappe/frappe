<template>
	<div class="pfb-stepper" :class="{ 'pfb-stepper--sm': sm }">
		<input
			class="form-control form-control-sm pfb-stepper-input"
			type="number"
			:min="min"
			:value="value"
			:placeholder="placeholder"
			@change="(e) => $emit('input', e.target.value)"
			@keydown.up.prevent="$emit('increment')"
			@keydown.down.prevent="$emit('decrement')"
		/>
		<span class="pfb-stepper-suffix">
			<span v-if="unit && value !== '' && value != null" class="pfb-stepper-unit">{{
				unit
			}}</span>
			<button
				type="button"
				class="es-button"
				data-variant="ghost"
				data-size="xs"
				data-icon-button="true"
				tabindex="-1"
				:aria-label="__('Decrease')"
				@click="$emit('decrement')"
				v-html="frappe.utils.icon('minus', 'xs')"
			></button>
			<button
				type="button"
				class="es-button"
				data-variant="ghost"
				data-size="xs"
				data-icon-button="true"
				tabindex="-1"
				:aria-label="__('Increase')"
				@click="$emit('increment')"
				v-html="frappe.utils.icon('plus', 'xs')"
			></button>
		</span>
	</div>
</template>

<script setup>
defineProps({
	value: { type: [Number, String], default: "" },
	min: { type: [Number, String], default: 0 },
	unit: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	sm: { type: Boolean, default: false },
});
defineEmits(["decrement", "increment", "input"]);
</script>

<style scoped>
.pfb-stepper {
	position: relative;
	width: 100%;
}

.pfb-stepper--sm {
	width: 96px;
}

.pfb-stepper-input {
	width: 100%;
	padding-right: 72px;
	font-variant-numeric: tabular-nums;
	-moz-appearance: textfield;
}

.pfb-stepper--sm .pfb-stepper-input {
	padding-right: 64px;
}

.pfb-stepper-input::-webkit-inner-spin-button,
.pfb-stepper-input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-stepper-suffix {
	position: absolute;
	top: 0;
	right: 2px;
	bottom: 0;
	display: flex;
	align-items: center;
	gap: 0;
}

.pfb-stepper-unit {
	margin-right: calc(var(--spacing) * 1);
	font-size: var(--text-sm);
	color: var(--ink-gray-5);
}

.pfb-stepper-suffix .es-button {
	color: var(--ink-gray-5);
}

.pfb-stepper-suffix .es-button:hover {
	color: var(--ink-gray-8);
}
</style>
