<template>
	<InspectorRow :label="label" class="pfb-spacing-row">
		<div class="pfb-spacing-sides">
			<div v-for="side in sides" :key="side" class="pfb-spacing-side">
				<input
					type="number"
					min="0"
					step="any"
					:value="modelValue?.[side] ?? 0"
					:title="side_labels[side]"
					@change="(e) => set_side(side, e.target.value)"
				/>
				<span>{{ side_labels[side].charAt(0) }}</span>
			</div>
		</div>
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";

const props = defineProps({
	label: { type: String, required: true },
	modelValue: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const sides = ["top", "right", "bottom", "left"];
const side_labels = {
	top: __("Top"),
	right: __("Right"),
	bottom: __("Bottom"),
	left: __("Left"),
};

function set_side(side, v) {
	const n = Math.max(0, parseFloat(v) || 0);
	emit("update:modelValue", {
		top: 0,
		right: 0,
		bottom: 0,
		left: 0,
		...props.modelValue,
		[side]: n,
	});
}
</script>

<style scoped>
.pfb-spacing-sides {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 4px;
	min-width: 0;
}

.pfb-spacing-side {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 2px;
	min-width: 0;
}

.pfb-spacing-row {
	align-items: start;
}

.pfb-spacing-row :deep(.pfb-insp-label) {
	line-height: var(--input-height);
}

.pfb-spacing-side input {
	box-sizing: border-box;
	width: 100%;
	min-width: 0;
	height: var(--input-height);
	padding: 4px 2px;
	text-align: center;
	font-size: var(--text-sm);
	font-weight: 500;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--subtle-accent);
	color: var(--text-color);
	outline: none;
}

.pfb-spacing-side input:focus {
	background: var(--fg-color);
}

.pfb-spacing-side input::-webkit-inner-spin-button,
.pfb-spacing-side input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-spacing-side span {
	font-size: var(--text-tiny);
	color: var(--text-muted);
}
</style>
