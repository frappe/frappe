<!-- The Favourite column: the person's own star on the row, toggled in place. -->
<template>
	<FavouriteStar :favourited="isStarred(doctype, name, user)" @click.stop.prevent="toggle" />
</template>

<script setup lang="ts">
import { toast } from "frappe-ui";
import { inject } from "vue";
import { errorMessage } from "@/recordPage";
import { isStarred, toggleStar } from "@/list/favouriteStars";
import type { Boot } from "@/boot";
import FavouriteStar from "../favourite/FavouriteStar.vue";

const props = defineProps<{ doctype: string; name: string }>();
const user = inject<Boot>("boot")!.session.user.name;

async function toggle() {
	try {
		await toggleStar(props.doctype, props.name, user);
	} catch (failure) {
		toast.error(errorMessage(failure));
	}
}
</script>
