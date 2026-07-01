<template>
	<div class="pfb-box">
		<label v-for="side in sides" :key="side" class="pfb-box-cell" :title="__(side)">
			<span>{{ side[0].toUpperCase() }}</span>
			<input
				type="number"
				min="0"
				placeholder="0"
				:value="modelValue && modelValue[side] ? modelValue[side] : ''"
				@change="(e) => update(side, e.target.value)"
			/>
		</label>
	</div>
</template>

<script setup>
// Compact top / right / bottom / left number inputs bound to a single
// { top, right, bottom, left } object. Emits null once every side is 0 so the
// caller can drop the key entirely.
const props = defineProps({
	modelValue: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const sides = ["top", "right", "bottom", "left"];

function update(side, raw) {
	const next = { top: 0, right: 0, bottom: 0, left: 0, ...(props.modelValue || {}) };
	next[side] = Math.max(0, parseInt(raw) || 0);
	emit("update:modelValue", sides.every((s) => !next[s]) ? null : next);
}
</script>

<style scoped>
.pfb-box {
	display: flex;
	gap: 4px;
}

.pfb-box-cell {
	display: flex;
	align-items: center;
	gap: 3px;
	flex: 1;
	min-width: 0;
	margin: 0;
}

.pfb-box-cell span {
	font-size: var(--text-tiny);
	color: var(--text-muted);
}

.pfb-box-cell input {
	width: 100%;
	min-width: 0;
	text-align: center;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--fg-color);
	color: var(--text-color);
	padding: 3px 2px;
	font-size: var(--text-sm);
	outline: none;
}

.pfb-box-cell input:focus {
	border-color: var(--primary);
}
</style>
