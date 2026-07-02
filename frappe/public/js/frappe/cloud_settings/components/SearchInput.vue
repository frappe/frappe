<!--
  SearchInput — a search box styled like a frappe-ui control (icon + input).
  Radius and fill match the SettingsDialog (var(--radius), var(--control-bg)).
-->
<template>
	<div class="cs-search" :class="{ focused }">
		<svg class="icon icon-sm cs-search-icon"><use href="#icon-search"></use></svg>
		<input
			type="text"
			class="cs-search-input"
			:value="modelValue"
			:placeholder="placeholder"
			@input="$emit('update:modelValue', $event.target.value)"
			@focus="focused = true"
			@blur="focused = false"
		/>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);

const focused = ref(false);
</script>

<style scoped>
.cs-search {
	display: flex;
	align-items: center;
	gap: 8px;
	flex: 1;
	height: 32px;
	padding: 0 10px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--control-bg);
	transition: border-color 0.1s, background 0.1s;
}

.cs-search.focused {
	border-color: var(--gray-500);
	background: var(--fg-color);
}

.cs-search-icon {
	flex-shrink: 0;
	color: var(--gray-400);
}

.cs-search-input {
	flex: 1;
	min-width: 0;
	border: none;
	background: transparent;
	outline: none;
	font-size: var(--text-sm);
	color: var(--text-color);
}

.cs-search-input::placeholder {
	color: var(--gray-400);
}
</style>
