<template>
	<div class="section-insert">
		<div class="section-insert-line"></div>
		<button class="section-insert-btn" @click="$emit('insert')">
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
	gap: 8px;
	height: 1.5rem;
	opacity: 0;
	transition: opacity 0.15s ease;
}

.section-insert:hover {
	opacity: 1;
}

.section-insert-line {
	flex: 1;
	height: 1px;
	background: var(--gray-400);
	border-radius: 1px;
}

.section-insert-btn {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 3px;
	padding: 1px 8px;
	border-radius: var(--radius);
	border: 1px solid var(--gray-300);
	background: var(--fg-color);
	color: var(--text-muted);
	cursor: pointer;
	font-size: var(--text-xs);
	font-weight: var(--weight-regular);
	white-space: nowrap;
	box-shadow: none;
}

.section-insert:hover .section-insert-line {
	background: var(--gray-400);
}

.section-insert:hover .section-insert-btn {
	border-color: var(--gray-400);
	color: var(--text-color);
}
</style>
