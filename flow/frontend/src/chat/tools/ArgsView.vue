<template>
	<div
		v-if="!blank(value)"
		class="max-h-[260px] overflow-auto px-3.5 py-2 text-sm leading-relaxed text-ink-gray-7"
	>
		<DataView :value="value" />
	</div>
</template>

<script setup>
import { computed } from "vue";

import DataView from "./DataView.vue";
import { blank } from "./result.js";

// A custom tool's approval card: the prompt its author wrote, else its arguments in words.
const props = defineProps({
	arguments: { type: Object, default: () => ({}) },
	call: { type: Object, default: null },
});

// without a prompt of its own, the server sends the arguments as JSON
const value = computed(() => {
	const body = (props.call?.prompt ?? "").split("\n").slice(1).join("\n").trim();
	try {
		JSON.parse(body);
		return props.arguments;
	} catch {
		return body || props.arguments;
	}
});
</script>
