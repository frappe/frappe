<template>
	<!-- display: contents, so the header lays out the Combobox; it holds the clock to focus again -->
	<div v-if="hasChats" ref="root" class="contents">
		<Combobox
			v-model:open="open"
			v-model:query="search"
			:model-value="flow.state.sessionId"
			:options="options"
			:filterable="false"
			:loading="flow.state.sessionsLoading && !options.length"
			:empty-text="search ? 'No matching chats' : 'No chats yet'"
			placeholder="Search chats…"
			align="end"
			@update:model-value="choose"
		>
			<template #trigger>
				<Button
					variant="ghost"
					icon="lucide-history"
					title="Recent chats"
					aria-label="Recent chats"
				/>
			</template>
			<template v-if="flow.state.sessionsMore" #footer>
				<div class="border-t border-outline-gray-1 p-1">
					<Button
						variant="ghost"
						class="w-full"
						:label="flow.state.sessionsLoading ? 'Loading more…' : 'Load more'"
						:disabled="flow.state.sessionsLoading"
						@click="flow.loadMoreSessions()"
					/>
				</div>
			</template>
		</Combobox>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue";
import { Button } from "frappe-ui/src/components/Button";
import { Combobox } from "frappe-ui/src/components/Combobox";

import { useDebouncedValue } from "../debounce.js";

// The chats, under a clock in a header with no sidebar beside it: the sidebar's list and search
const flow = inject("flow");
const open = ref(false);
const search = ref("");
const root = ref(null);
// past a full page the host searches too, as it does for the sidebar's box
watch(useDebouncedValue(search, 150), (q) => flow.searchSessions(q));
// a search left in the box gives way to the whole list, and the keyboard goes back to the clock:
// frappe-ui's Combobox returns focus to none, and can't reach a #trigger of its caller's
watch(open, (shown) => {
	if (shown) return;
	search.value = "";
	nextTick(() => root.value?.querySelector("button")?.focus());
});

// a user with no chats yet has nothing to list; a search that matched none keeps its box
const hasChats = computed(
	() => flow.state.sessions.length > 0 || Boolean(flow.state.sessionQuery),
);
// matched by title only: the Combobox's own filter matches each chat's id too
const options = computed(() => {
	const q = search.value.trim().toLowerCase();
	return flow.state.sessions
		.map((session) => ({ label: flow.sessionTitle(session), value: session.session_id }))
		.filter((option) => !q || option.label.toLowerCase().includes(q));
});

function choose(id) {
	open.value = false;
	if (id && id !== flow.state.sessionId) flow.openSession(id);
}
</script>
