<!-- One tag as a pill with its colour dot; the slot holds what follows the name (Remove). -->
<template>
	<span
		class="group/tag flex items-center gap-1.5 rounded-full border border-outline-gray-2 py-0.5 pl-2 text-sm text-ink-gray-7"
	>
		<span class="size-1.5 shrink-0 rounded-full" :class="tagColor(tag)" aria-hidden="true" />
		{{ tag }}
		<slot />
	</span>
</template>

<script setup lang="ts">
import { tagColor } from "./people";

defineProps<{ tag: string }>();
</script>
