<template>
	<Badge theme="gray" variant="outline" size="lg" class="min-w-0 max-w-40 gap-1.5">
		<span class="size-2 shrink-0 rounded-full" :class="resolvedColorToken" />
		<span :title="label" class="min-w-0 truncate text-ink-gray-7">{{ label }}</span>
		<slot name="suffix" />
	</Badge>
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import { computed } from "vue";
import { colorToken } from "./colors";
import type { TagColor } from "./types";

const props = defineProps<{ label: string; color?: TagColor }>();
const resolvedColorToken = computed(() => colorToken(props.color));
</script>
