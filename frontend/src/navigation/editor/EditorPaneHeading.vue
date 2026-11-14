<!-- The right pane's heading: what the row is, and whose. -->
<template>
	<div class="mb-5 flex items-center gap-3">
		<span class="grid size-8 shrink-0 place-items-center rounded-5 bg-surface-gray-2">
			<Icon :name="icon" class="text-ink-gray-7" />
		</span>
		<div class="min-w-0">
			<p class="truncate text-base font-semibold text-ink-gray-8">{{ title }}</p>
			<p class="text-sm text-ink-gray-5">{{ origin }}</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import Icon from "@/icons/Icon.vue";

defineProps<{ icon: string; title: string; origin: string }>();
</script>
