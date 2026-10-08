<template>
	<span class="inline-flex max-w-full flex-wrap items-center gap-1.5">
		<Tooltip v-if="from != null" :text="truncate(from).title">
			<span class="whitespace-nowrap font-semibold text-ink-gray-8">{{
				truncate(from).text
			}}</span>
		</Tooltip>
		<span v-else-if="showEmptyFrom" class="text-ink-gray-5">""</span>
		<span class="inline-flex items-center gap-1.5 whitespace-nowrap">
			<span v-if="from != null || showEmptyFrom" class="text-ink-gray-5">→</span>
			<Tooltip :text="truncate(to).title">
				<span class="font-semibold text-ink-gray-8">{{ truncate(to).text }}</span>
			</Tooltip>
			<slot />
		</span>
	</span>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { truncate } from "./utils";

defineProps<{
	from?: string | null;
	to: string;
	// history entries render a cleared "from" as "" instead of omitting it
	showEmptyFrom?: boolean;
}>();
</script>
