<template>
	<details v-if="structured" @toggle="open = $event.target.open">
		<summary class="cursor-pointer text-ink-gray-6">
			{{ Array.isArray(value) ? cellText(value) : "Details" }}
		</summary>
		<pre
			v-if="open"
			class="m-0 mt-1 max-h-[200px] overflow-auto whitespace-pre-wrap break-words font-mono text-xs"
			>{{ JSON.stringify(value, null, 2) }}</pre
		>
	</details>
	<span v-else :title="cellText(value)">{{ cellText(value) }}</span>
</template>

<script setup>
import { computed, ref } from "vue";

import { cellText } from "./result.js";

const props = defineProps({ value: { default: null } });
const open = ref(false);
const structured = computed(() => props.value !== null && typeof props.value === "object");
</script>
