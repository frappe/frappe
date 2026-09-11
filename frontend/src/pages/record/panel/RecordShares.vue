<!-- The `shares` built-in: who the record is shared with, read from `docinfo`. -->
<template>
	<PeopleRow
		label="Shared with"
		icon="lucide-share-2"
		:people="people"
		placeholder="Not shared"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { PanelContextKey, personOf } from "./context";
import PeopleRow from "./PeopleRow.vue";

const context = inject(PanelContextKey)!;

// A share with everyone has no person to draw; it is named as such.
const people = computed(() =>
	(context.docinfo.value?.shared ?? []).map((row) =>
		row.everyone
			? { id: "everyone", name: "Everyone" }
			: personOf(context.docinfo.value, row.user)
	)
);
</script>
