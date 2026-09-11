<!-- The `assignees` built-in: who the record is assigned to, read from `docinfo`. -->
<template>
	<PeopleRow
		label="Assigned to"
		icon="lucide-user"
		:people="people"
		placeholder="Not assigned"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { PanelContextKey, personOf } from "./context";
import PeopleRow from "./PeopleRow.vue";

const context = inject(PanelContextKey)!;

const people = computed(() =>
	(context.docinfo.value?.assignments ?? []).map((row) =>
		personOf(context.docinfo.value, row.owner)
	)
);
</script>
