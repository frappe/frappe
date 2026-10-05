<template>
	<div class="min-w-0">
		<div class="truncate">{{ item.label }}</div>
		<div v-if="item.description" class="truncate text-p-sm text-ink-gray-5">
			{{ item.description }}
		</div>
	</div>
</template>

<script setup lang="ts">
import type { AutomationCanvasOption } from "./types";

defineProps<{ item: AutomationCanvasOption }>();
</script>
