<template>
	<div
		class="lh-footer"
		:class="{ 'lh-footer--selected': store.selected_lh_footer.value }"
		@click.stop="select_footer"
	>
		<div v-if="letterhead.footer" v-html="letterhead.footer"></div>
		<div v-else class="lh-footer-empty">
			<span class="text-muted">{{ __("No Letter Head Footer — click to add") }}</span>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue";
import { useStore } from "../../stores";

let { letterhead } = useStore();
let store = inject("$store");

function select_footer() {
	store.selected_lh_footer.value = true;
	store.selected_letterhead.value = false;
	store.selected_field.value = null;
	store.selected_section.value = null;
}
</script>

<style scoped>
.lh-footer {
	position: relative;
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
	cursor: pointer;
	transition: border-color 0.15s;
}

.lh-footer:hover {
	border-color: var(--gray-300);
}

.lh-footer--selected {
	border-color: var(--primary);
}

.lh-footer-empty {
	display: flex;
	align-items: center;
	gap: 6px;
	color: var(--text-muted);
	font-size: var(--text-sm);
	padding: 0.5rem 0;
}
</style>
