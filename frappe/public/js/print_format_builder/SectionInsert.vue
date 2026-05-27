<template>
	<div class="section-insert" @click="$emit('insert')">
		<div class="section-insert-line"></div>
		<button
			class="section-insert-btn"
			:title="__('Add section here')"
			v-html="frappe.utils.icon('plus', 'xs')"
		></button>
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
	height: 1.25rem;
	cursor: pointer;
	opacity: 0;
	transition: opacity 0.15s ease;
}

.section-insert:hover {
	opacity: 1;
}

.section-insert-line {
	flex: 1;
	height: 1.5px;
	background: var(--gray-400);
	border-radius: 1px;
}

.section-insert-btn {
	flex-shrink: 0;
	width: 18px;
	height: 18px;
	border-radius: 50%;
	border: 1.5px solid var(--gray-400);
	background: var(--fg-color);
	color: var(--gray-600);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 0;
	margin: 0 4px;
	cursor: pointer;
	box-shadow: none;
}

.section-insert-btn:hover {
	background: var(--gray-200);
	color: var(--gray-800);
	border-color: var(--gray-500);
}
</style>
