<!-- Assigned To and Liked By: the users a JSON-list column names, as overlapping avatars. -->
<template>
	<div class="flex min-w-0 items-center -space-x-1.5">
		<Tooltip v-for="person in people" :key="person.id" :text="person.name">
			<Avatar
				:label="person.name"
				:image="person.image"
				size="sm"
				class="ring-1 ring-white"
			/>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { Avatar, Tooltip } from "frappe-ui";
import { computed } from "vue";
import { personOf } from "@/list/rowParts";

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
