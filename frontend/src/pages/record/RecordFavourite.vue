<!-- The `favourite` built-in: a star that toggles the reader's favourite, over a card naming
     everyone who favourited the record. -->
<template>
	<!-- Nobody yet, no card: an empty one would open as a blank panel. -->
	<Tooltip v-if="!favourites.length" text="Add to favourites">
		<FavouriteStar :favourited="favourited" @click="emit('toggle')" />
	</Tooltip>
	<HoverCard v-else :hover-delay="0.2" :leave-delay="0.2" side="bottom" align="start">
		<template #trigger>
			<FavouriteStar :favourited="favourited" @click="emit('toggle')" />
		</template>

		<template #default>
			<div class="flex min-w-44 max-w-64 flex-col gap-2 p-3" data-favourites>
				<div v-for="person in favourites" :key="person.id" class="flex items-center gap-2">
					<Avatar :label="person.name" :image="person.image" size="md" />
					<span class="truncate text-p-base text-ink-gray-8">{{ person.name }}</span>
				</div>
			</div>
		</template>
	</HoverCard>
</template>

<script setup lang="ts">
import { Avatar, HoverCard, Tooltip } from "frappe-ui";
import FavouriteStar from "@/pages/favourite/FavouriteStar.vue";
import type { Person } from "./panel/people";

defineProps<{ favourites: Person[]; favourited: boolean }>();

const emit = defineEmits<{ toggle: [] }>();
</script>
