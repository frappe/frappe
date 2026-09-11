<!-- One people row, `assignees` or `shares`: a label named by an icon, then the people
     as avatars. Always drawn; an empty row says so instead of vanishing. -->
<template>
	<div class="grid grid-cols-[130px_1fr] items-center gap-2">
		<span class="flex min-w-0 items-center gap-2 truncate text-base text-ink-gray-5">
			<span class="size-4 shrink-0" :class="icon" aria-hidden="true" />
			{{ label }}
		</span>

		<span v-if="!people.length" class="truncate px-1.5 py-1 text-base text-ink-gray-4">
			{{ placeholder }}
		</span>
		<span v-else class="flex min-w-0 items-center gap-1 px-1.5 py-1">
			<span class="flex -space-x-1.5">
				<Tooltip v-for="person in people" :key="person.id" :text="person.name">
					<Avatar
						class="ring-2 ring-outline-base"
						:label="person.name"
						:image="person.image"
						size="sm"
					/>
				</Tooltip>
			</span>
			<!-- One person has room for a name; a stack speaks through its tooltips. -->
			<span v-if="people.length === 1" class="truncate text-base text-ink-gray-8">
				{{ people[0].name }}
			</span>
		</span>
	</div>
</template>

<script setup lang="ts">
import { Avatar, Tooltip } from "frappe-ui";

defineProps<{
	label: string;
	/** A lucide class, `lucide-user`. */
	icon: string;
	people: { id: string; name: string; image?: string }[];
	placeholder: string;
}>();
</script>
