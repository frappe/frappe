<!-- The assigned-to editor: the avatar stack as the trigger of a user picker. -->
<template>
	<MultiSelect
		:modelValue="assigned"
		:options="options"
		:query="query"
		:loading="loading"
		:filterable="false"
		:empty-text="error || 'No users found'"
		placeholder="Assign to…"
		@update:modelValue="reassign"
		@update:query="onQuery"
		@update:open="onOpen"
	>
		<template #trigger="{ open }">
			<button
				type="button"
				class="flex w-fit min-w-0 items-center gap-1 rounded-1 px-1.5 py-1 transition hover:bg-surface-gray-2"
				:aria-label="summary"
				data-assign
			>
				<PeopleAvatars :people="assignees" placeholder="Add people…" />
				<span
					v-if="assignees.length"
					:class="[
						'lucide-chevron-down size-3.5 text-ink-gray-5 transition-transform',
						open && 'rotate-180',
					]"
				/>
			</button>
		</template>

		<template #item-prefix="{ item }">
			<Avatar :label="item.label" :image="(item as SearchOption).image" size="sm" />
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Avatar, MultiSelect } from "frappe-ui";
import type { Person } from "./people";
import { listDiff } from "./people";
import PeopleAvatars from "./PeopleAvatars.vue";
import { useUserSearch, type SearchOption } from "./remoteSearch";

const props = defineProps<{
	assignees: Person[];
	call: (method: string, params?: Record<string, any>) => Promise<any>;
}>();

const emit = defineEmits<{ assign: [string]; unassign: [string] }>();

const assigned = computed(() => props.assignees.map(({ id }) => id));

const pinned = computed<SearchOption[]>(() =>
	props.assignees.map(({ id, name, image }) => ({ label: name, value: id, image }))
);

const { options, loading, error, search, searchSoon } = useUserSearch(props.call, pinned);

// Listening to the query owns it, so every open resets it and the list.
const query = ref("");

function onOpen(open: boolean) {
	if (!open) return;
	query.value = "";
	search("");
}

function onQuery(text: string) {
	query.value = text;
	searchSoon(text);
}

const summary = computed(() =>
	props.assignees.length
		? `Assigned to ${props.assignees.map(({ name }) => name).join(", ")}`
		: "Assign to…"
);

// The selection is server state: each pick fires one write and the re-read repaints it.
function reassign(picked: (string | number)[]) {
	const { added, dropped } = listDiff(picked.map(String), assigned.value);
	added.forEach((user) => emit("assign", user));
	dropped.forEach((user) => emit("unassign", user));
}
</script>
