<template>
	<div class="pfb-stepper" :class="{ 'pfb-stepper--sm': sm }">
		<button type="button" @click="$emit('decrement')">−</button>
		<input
			class="pfb-stepper-input"
			type="number"
			:min="min"
			:value="value"
			:placeholder="placeholder"
			@change="(e) => $emit('input', e.target.value)"
		/>
		<span v-if="unit" class="pfb-stepper-unit">{{ unit }}</span>
		<button type="button" @click="$emit('increment')">+</button>
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
	display: inline-flex;
	align-items: center;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	overflow: hidden;
	background: var(--subtle-accent);
	width: 100%;
}

.pfb-stepper--sm {
	width: auto;
}

.pfb-stepper--sm .pfb-stepper-input {
	width: 30px;
	flex: none;
}

.pfb-stepper button {
	padding: 4px 8px;
	border: none;
	background: transparent;
	cursor: pointer;
	font-size: 14px;
	color: var(--text-muted);
	line-height: 1;
	flex-shrink: 0;
}

.pfb-stepper button:hover {
	background: var(--gray-100);
	color: var(--text-color);
}

.pfb-stepper-input {
	flex: 1;
	min-width: 0;
	width: 100%;
	text-align: center;
	font-size: var(--text-sm);
	font-weight: 500;
	border: none;
	border-left: 1px solid var(--border-color);
	border-right: 1px solid var(--border-color);
	background: transparent;
	color: var(--text-color);
	padding: 4px 2px;
	outline: none;
}

.pfb-stepper-input:focus {
	background: var(--fg-color);
}

.pfb-stepper-input::-webkit-inner-spin-button,
.pfb-stepper-input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-stepper-unit {
	font-size: var(--text-tiny);
	color: var(--text-muted);
	padding: 0 6px 0 2px;
}
</style>
