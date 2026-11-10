<!-- Assigned To and Liked By: the users a JSON-list column names, drawn as the record panel draws people. -->
<template>
	<PeopleAvatars :people="people" placeholder="" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { personOf } from "@/list/rowParts";
import PeopleAvatars from "../record/panel/PeopleAvatars.vue";

const props = defineProps<{ value: unknown }>();

const people = computed(() => idsOf(props.value).map(personOf));

function idsOf(value: unknown): string[] {
	try {
		const ids = typeof value === "string" ? JSON.parse(value) : [];
		return Array.isArray(ids) ? ids.filter((id) => typeof id === "string" && id) : [];
	} catch {
		return [];
	}
}
</script>
