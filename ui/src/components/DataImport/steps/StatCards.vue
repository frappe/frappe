<template>
	<div
		class="grid w-full gap-3"
		role="list"
		:aria-label="label"
		:style="{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }"
	>
		<div
			v-for="stat in stats"
			:key="stat.label"
			class="flex min-w-0 flex-col gap-0.5 rounded-5 border border-outline-gray-2 px-4 py-2.5"
			role="listitem"
		>
			<div class="flex h-5 items-center justify-between gap-1">
				<span class="truncate text-sm-medium text-ink-gray-5">{{ stat.label }}</span>
				<Button
					v-if="stat.download"
					class="-me-1.5 shrink-0"
					variant="ghost"
					size="xs"
					icon="lucide-download"
					:title="stat.download.title"
					:aria-label="stat.download.title"
					@click="stat.download.onClick"
				/>
			</div>
			<div class="text-xl-semibold" :class="stat.class || 'text-ink-gray-8'">
				{{ stat.value }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";

export interface Stat {
	label: string;
	value: number;
	class?: string;
	download?: { title: string; onClick: () => void };
}

defineProps<{ stats: Stat[]; label: string }>();
</script>
