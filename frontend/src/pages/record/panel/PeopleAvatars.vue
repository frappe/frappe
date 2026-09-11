<!-- A stack of people as avatars, or the placeholder when there is nobody. -->
<template>
	<span v-if="!people.length" class="truncate text-base text-ink-gray-4">{{ placeholder }}</span>
	<span v-else class="flex min-w-0 items-center gap-1">
		<span class="flex -space-x-1.5">
			<Tooltip v-for="person in visible" :key="person.id" :text="person.name">
				<Avatar
					class="ring-2 ring-outline-base"
					:label="person.name"
					:image="person.image"
					size="sm"
				/>
			</Tooltip>
			<span
				v-if="overflow"
				class="z-10 grid size-5 place-items-center rounded-full bg-surface-gray-3 text-p-xs-medium text-ink-gray-7"
			>
				+{{ overflow }}
			</span>
		</span>
		<!-- One person has room for a name; a stack speaks through its tooltips. -->
		<span v-if="people.length === 1" class="truncate text-base text-ink-gray-8">
			{{ people[0].name }}
		</span>
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Avatar, Tooltip } from "frappe-ui";
import type { Person } from "./people";

const MAX_AVATARS = 3;

const props = defineProps<{ people: Person[]; placeholder: string }>();

const visible = computed(() => props.people.slice(0, MAX_AVATARS));
const overflow = computed(() => Math.max(0, props.people.length - MAX_AVATARS));
</script>
