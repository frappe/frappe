<!-- The `favourite` built-in: a star that toggles the reader's favourite, over a card naming
     everyone who favourited the record. -->
<template>
	<DefineStar>
		<Button
			variant="ghost"
			:label="favourited ? 'Remove from favourites' : 'Add to favourites'"
			:aria-pressed="favourited"
			data-favourite
			@click="emit('toggle')"
		>
			<template #icon>
				<!-- Drawn here, not off a lucide mask, so the favourited stroke can thicken. -->
				<svg
					class="size-4"
					:class="favourited ? 'fill-ink-amber-4 stroke-ink-amber-4' : 'text-ink-gray-7'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					:stroke-width="favourited ? 2.5 : 1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path
						d="M12 2.5l2.9 5.88 6.6.96-4.75 4.63 1.12 6.53L12 17.4l-5.87 3.1 1.12-6.53L2.5 9.34l6.6-.96z"
					/>
				</svg>
			</template>
		</Button>
	</DefineStar>

	<!-- Nobody yet, no card: an empty one would open as a blank panel. -->
	<Tooltip v-if="!favourites.length" text="Add to favourites">
		<Star />
	</Tooltip>
	<HoverCard v-else :hover-delay="0.2" :leave-delay="0.2" side="bottom" align="start">
		<template #trigger>
			<Star />
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
import { createReusableTemplate } from "@vueuse/core";
import { Avatar, Button, HoverCard, Tooltip } from "frappe-ui";
import type { Person } from "./panel/people";

defineProps<{ favourites: Person[]; favourited: boolean }>();

const emit = defineEmits<{ toggle: [] }>();

const [DefineStar, Star] = createReusableTemplate();
</script>
