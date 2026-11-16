<template>
	<div class="flex flex-col gap-0.5">
		<button
			v-for="option in options"
			:key="String(option.value)"
			type="button"
			class="group flex items-center gap-3 rounded-6 px-2 py-2.5 text-start transition-colors hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2"
			@click="emit('choose', option)"
		>
			<span
				class="flex size-8 shrink-0 items-center justify-center rounded-5 bg-surface-gray-2 text-ink-gray-7 transition-colors group-hover:bg-surface-base"
			>
				<slot name="icon" :option="option">
					<span v-if="option.icon" :class="option.icon" class="size-4" />
				</slot>
			</span>
			<span class="min-w-0 flex-1">
				<span class="block text-p-sm font-medium text-ink-gray-9">
					{{ option.label }}
				</span>
				<span v-if="option.description" class="block text-p-xs text-ink-gray-6">
					{{ option.description }}
				</span>
			</span>
			<span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4" />
		</button>
	</div>
</template>

<script setup lang="ts">
import type { ListOption } from "./types";

/** One choice out of a few that each deserve a line of explanation; choosing moves on. */
defineProps<{ options: ListOption[] }>();
const emit = defineEmits<{ choose: [option: ListOption] }>();
</script>
