<!-- The body of the share dialog, opened through `page.dialog.open`: a user picker above the
     people the record is shared with. The list is live, so a share shows as soon as it is re-read. -->
<template>
	<div class="flex flex-col gap-3" data-share-dialog>
		<Combobox
			autofocus
			trigger="button"
			:modelValue="null"
			:query="query"
			:options="options"
			:loading="loading"
			:filterable="false"
			:empty-text="error || 'No users found'"
			placeholder="Add people by name or email"
			@update:modelValue="shareWith"
			@update:query="onQuery"
			@update:open="onOpen"
		>
			<template #item-prefix="{ item }">
				<Avatar :label="item.label" :image="(item as SearchOption).image" size="sm" />
			</template>
		</Combobox>

		<div class="flex flex-col">
			<div
				v-for="person in shared"
				:key="person.id"
				class="group/share flex items-center gap-2 py-1.5"
				data-shared-with
			>
				<Avatar :label="person.name" :image="person.image" size="md" />
				<span class="truncate text-base text-ink-gray-8">{{ person.name }}</span>
				<span class="ml-auto text-base text-ink-gray-5">
					{{ person.canWrite ? "Can edit" : "Can view" }}
				</span>
				<Button
					class="opacity-0 transition focus-visible:opacity-100 group-hover/share:opacity-100"
					icon="lucide-x"
					variant="ghost"
					:aria-label="`Stop sharing with ${person.name}`"
					@click="actions.unshare(person.id, person.everyone)"
				/>
			</div>

			<p v-if="!shared.length" class="py-1.5 text-base text-ink-gray-5">
				This record is not shared with anyone.
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Avatar, Button, Combobox } from "frappe-ui";
import type { PanelContext } from "./context";
import { sharedWith } from "./people";
import { peopleActions } from "./peopleActions";
import { useUserSearch, type SearchOption } from "./remoteSearch";

// `close` is the host's; the dialog stays open across shares, so it is never called here.
const props = defineProps<{ context: PanelContext; close: (result?: any) => void }>();

const actions = peopleActions(props.context);

const shared = computed(() => sharedWith(props.context.docinfo.value));

const pinned = computed<SearchOption[]>(() =>
	shared.value
		.filter((person) => !person.everyone)
		.map(({ id, name, image }) => ({ label: name, value: id, image }))
);

const { options, loading, error, search, searchSoon } = useUserSearch(
	props.context.controller.page.call,
	pinned
);

// Listening to the query owns it, and a pick writes the label into it, so every open resets both.
const query = ref("");

function onOpen(shown: boolean) {
	if (!shown) return;
	query.value = "";
	search("");
}

function onQuery(text: string) {
	query.value = text;
	searchSoon(text);
}

function shareWith(user: string | number | null) {
	if (user) actions.share(String(user));
}
</script>
