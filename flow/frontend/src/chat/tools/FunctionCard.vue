<template>
	<div v-if="lines.length" class="overflow-x-auto px-3 py-2.5">
		<table class="border-collapse text-left text-sm">
			<tbody class="text-ink-gray-7">
				<tr v-for="([label, value], i) in lines" :key="i" class="align-top">
					<td class="whitespace-nowrap py-0.5 pr-3 text-ink-gray-5">{{ label }}</td>
					<td class="py-0.5">{{ value }}</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup>
import { computed } from "vue";

// a function's approval card: the server's prompt names its records by title, one "Label: value" line each
const props = defineProps({
	arguments: { type: Object, default: () => ({}) },
	call: { type: Object, required: true },
});
const lines = computed(() =>
	(props.call.prompt ?? "")
		.split("\n")
		.slice(1)
		.filter((line) => line.trim())
		.map((line) => {
			const at = line.indexOf(": ");
			return at < 0 ? ["", line] : [line.slice(0, at), line.slice(at + 2)];
		})
);
</script>
