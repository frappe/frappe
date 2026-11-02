<template>
	<Combobox
		v-if="hasChats"
		v-model:open="open"
		v-model:query="search"
		:model-value="flow.state.sessionId"
		:options="options"
		:loading="flow.state.sessionsLoading && !options.length"
		:empty-text="search ? 'No matching chats' : 'No chats yet'"
		placeholder="Search chats…"
		align="end"
		@update:model-value="choose"
	>
		<template #trigger>
			<Button variant="ghost" icon="lucide-history" title="Recent chats" aria-label="Recent chats" />
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
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Combobox } from "frappe-ui/src/components/Combobox"

import { useDebouncedValue } from "../debounce.js"

// The chats, under a clock in a header with no sidebar beside it: the sidebar's list and search
const flow = inject("flow")
const open = ref(false)
const search = ref("")
// past a full page the host searches too, as it does for the sidebar's box
watch(useDebouncedValue(search, 150), (q) => flow.searchSessions(q))
// a search left in the box gives way to the whole list
watch(open, (shown) => shown || (search.value = ""))

// a user with no chats yet has nothing to list; a search that matched none keeps its box
const hasChats = computed(() => flow.state.sessions.length > 0 || Boolean(flow.state.sessionQuery))
const options = computed(() =>
	flow.state.sessions.map((session) => ({ label: flow.sessionTitle(session), value: session.session_id }))
)

function choose(id) {
	open.value = false
	if (id && id !== flow.state.sessionId) flow.openSession(id)
}
</script>
