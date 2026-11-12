<!-- The `favourite` built-in: a star that toggles the reader's favourite, over a card naming
     everyone who favourited the record. -->
<template>
	<!-- Nobody yet, no card: an empty one would open as a blank panel. -->
	<Tooltip
		v-if="!FavouriteCard || !favourites.length"
		:text="favouriteWording(favourited).label"
	>
		<FavouriteStar :favourited="favourited" @click="emit('toggle')" />
	</Tooltip>
	<FavouriteCard
		v-else
		:favourites="favourites"
		:favourited="favourited"
		@toggle="emit('toggle')"
	/>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { shallowRef, watchEffect, type Component } from "vue";
import FavouriteStar from "@/pages/favourite/FavouriteStar.vue";
import { favouriteWording } from "@/pages/favourite/favouriteWording";
import type { Person } from "./panel/people";

const props = defineProps<{ favourites: Person[]; favourited: boolean }>();

const emit = defineEmits<{ toggle: [] }>();

// The card's hover popper is kept out of pages that never show one (a list has no people).
const FavouriteCard = shallowRef<Component | null>(null);
watchEffect(async () => {
	if (props.favourites.length && !FavouriteCard.value)
		FavouriteCard.value = (await import("./FavouriteCard.vue")).default;
});
</script>
