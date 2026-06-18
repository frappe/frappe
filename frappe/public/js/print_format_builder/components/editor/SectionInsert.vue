<template>
	<div class="section-insert" @click="$emit('insert')">
		<div class="section-insert-line"></div>
		<button class="section-insert-btn">
			<span v-html="frappe.utils.icon('plus', 'xs')"></span>
			{{ __("Add Section") }}
		</button>
		<div class="section-insert-line"></div>
	</div>
</template>

<script setup>
defineEmits(["insert"]);
</script>

<style scoped>
.section-insert {
	display: flex;
	align-items: center;
	height: 1.75rem;
	cursor: pointer;
	opacity: 0;
	transition: opacity 0.15s ease;
	padding: 4px 0;
}

.section-insert:hover,
.section-insert.section-insert--visible {
	opacity: 1;
}

.section-insert-line {
	flex: 1;
	height: 1.5px;
	background: var(--primary);
	border-radius: 1px;
	opacity: 0.4;
}

.section-insert-btn {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 3px;
	height: 22px;
	border-radius: var(--border-radius);
	border: 1px solid var(--primary);
	background: var(--fg-color);
	color: var(--primary);
	padding: 0 7px;
	margin: 0 6px;
	cursor: pointer;
	font-size: var(--text-xs);
	font-weight: var(--weight-medium);
	white-space: nowrap;
	box-shadow: none;
}

.section-insert-btn:hover {
	background: var(--blue-50);
}
</style>
