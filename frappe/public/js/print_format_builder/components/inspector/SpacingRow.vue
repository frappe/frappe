<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<div class="pfb-spacing-controls">
			<Stepper
				v-if="!split"
				:value="uniform_value ?? ''"
				:placeholder="is_mixed ? __('Mixed') : '0'"
				:unit="unit"
				@decrement="adjust_all(-step)"
				@increment="adjust_all(step)"
				@input="set_all"
			/>
			<div v-else class="pfb-spacing-sides">
				<div v-for="side in sides" :key="side" class="pfb-spacing-side">
					<input
						type="number"
						min="0"
						:value="modelValue?.[side] ?? 0"
						:title="side_labels[side]"
						@change="(e) => set_side(side, e.target.value)"
					/>
					<span>{{ side_labels[side].charAt(0) }}</span>
				</div>
			</div>
			<button
				type="button"
				class="pfb-spacing-toggle"
				:class="{ active: split }"
				:title="split ? __('Set all sides together') : __('Set each side separately')"
				@click="split = !split"
			>
				<svg
					width="14"
					height="14"
					viewBox="0 0 14 14"
					fill="none"
					stroke="currentColor"
					stroke-width="1.3"
					stroke-linecap="round"
				>
					<path d="M4 1.5h6M12.5 4v6M10 12.5H4M1.5 10V4" />
					<rect x="5.5" y="5.5" width="3" height="3" rx="0.5" />
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import Stepper from "./Stepper.vue";

const props = defineProps({
	label: { type: String, required: true },
	modelValue: { type: Object, default: null },
	step: { type: Number, default: 4 },
	unit: { type: String, default: "px" },
});
const emit = defineEmits(["update:modelValue"]);

const sides = ["top", "right", "bottom", "left"];
const side_labels = {
	top: __("Top"),
	right: __("Right"),
	bottom: __("Bottom"),
	left: __("Left"),
};

const side_values = computed(() => sides.map((s) => props.modelValue?.[s] ?? 0));
const is_mixed = computed(() => new Set(side_values.value).size > 1);
const uniform_value = computed(() => (is_mixed.value ? null : side_values.value[0]));

const split = ref(true);
let own_update = false;

watch(
	() => props.modelValue,
	() => {
		if (own_update) {
			own_update = false;
		} else {
			split.value = true;
		}
	}
);

function next(value) {
	own_update = true;
	emit("update:modelValue", value);
}

function set_all(v) {
	const n = Math.max(0, parseInt(v) || 0);
	next({ top: n, right: n, bottom: n, left: n });
}

function adjust_all(delta) {
	const base = is_mixed.value ? Math.max(...side_values.value) : side_values.value[0];
	set_all(base + delta);
}

function set_side(side, v) {
	const n = Math.max(0, parseInt(v) || 0);
	next({
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
.pfb-spacing-controls {
	display: flex;
	align-items: flex-start;
	gap: 4px;
	min-width: 0;
}

.pfb-spacing-controls > .pfb-stepper {
	flex: 1;
}

.pfb-spacing-sides {
	flex: 1;
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

.pfb-spacing-side input {
	width: 100%;
	min-width: 0;
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

.pfb-spacing-toggle {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 26px;
	height: 26px;
	padding: 0;
	border: none;
	border-radius: var(--radius);
	background: transparent;
	color: var(--text-muted);
	cursor: pointer;
}

.pfb-spacing-toggle:hover {
	background: var(--gray-100);
	color: var(--text-color);
}

.pfb-spacing-toggle.active {
	background: var(--subtle-fg);
	color: var(--text-color);
}
</style>
