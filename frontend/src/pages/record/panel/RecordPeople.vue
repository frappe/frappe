<!-- The `people` built-in: who the record is assigned to and shared with, read from `docinfo`. -->
<template>
	<PeopleRow
		label="Assigned to"
		icon="lucide-user"
		:people="assignees"
		placeholder="Not assigned"
	/>
	<PeopleRow
		label="Shared with"
		icon="lucide-share-2"
		:people="shares"
		placeholder="Not shared"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { PanelContextKey, personOf } from "./context";
import PeopleRow from "./PeopleRow.vue";

const context = inject(PanelContextKey)!;

const assignees = computed(() =>
	(context.docinfo.value?.assignments ?? []).map((row) =>
		personOf(context.docinfo.value, row.owner)
	)
);

// A share with everyone has no person to draw; it is named as such.
const shares = computed(() =>
	(context.docinfo.value?.shared ?? []).map((row) =>
		row.everyone
			? { id: "everyone", name: "Everyone" }
			: personOf(context.docinfo.value, row.user)
	)
);
</script>
