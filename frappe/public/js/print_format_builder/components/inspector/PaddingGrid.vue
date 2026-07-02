<template>
	<div class="pfb-padding-grid">
		<div v-for="side in sides" :key="side" class="pfb-padding-cell">
			<div class="pfb-padding-label">{{ side_labels[side] }}</div>
			<Stepper
				sm
				:value="modelValue?.[side] ?? 0"
				@decrement="adjust(side, -step)"
				@increment="adjust(side, step)"
				@input="(v) => set(side, v)"
			/>
		</div>
	</div>
</template>

<script setup>
import Stepper from "./Stepper.vue";

const props = defineProps({
	modelValue: { type: Object, default: () => ({}) },
	step: { type: Number, default: 4 },
});
const emit = defineEmits(["update:modelValue"]);

const sides = ["top", "right", "bottom", "left"];
const side_labels = { top: __("Top"), right: __("Right"), bottom: __("Bottom"), left: __("Left") };

function next(side, value) {
	emit("update:modelValue", {
		top: 0,
		right: 0,
		bottom: 0,
		left: 0,
		...props.modelValue,
		[side]: value,
	});
}

function adjust(side, delta) {
	const current = props.modelValue?.[side] ?? 0;
	next(side, Math.max(0, current + delta));
}

function set(side, v) {
	const n = parseInt(v);
	next(side, Math.max(0, isNaN(n) ? 0 : n));
}
</script>

<style scoped>
.pfb-padding-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 8px;
}

.pfb-padding-cell {
	display: flex;
	flex-direction: column;
	gap: 3px;
}

.pfb-padding-label {
	font-size: var(--text-tiny);
	color: var(--text-muted);
	text-align: center;
}
</style>
