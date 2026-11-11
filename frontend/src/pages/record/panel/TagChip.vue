<!-- One tag as Helpdesk draws it: an outline badge with its colour dot; the slot holds what follows the name (Remove). -->
<template>
	<Badge
		theme="gray"
		variant="outline"
		size="lg"
		class="group/tag min-w-0 max-w-40 gap-1.5 transition-colors duration-150 hover:bg-surface-gray-2"
	>
		<span
			class="size-2 shrink-0 rounded-full"
			:class="tagColorClass(tag)"
			aria-hidden="true"
		/>
		<span :title="tag" class="min-w-0 truncate text-ink-gray-7">{{ tag }}</span>
		<slot />
	</Badge>
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import { tagColorClass } from "@/tagColors";

defineProps<{ tag: string }>();
</script>
