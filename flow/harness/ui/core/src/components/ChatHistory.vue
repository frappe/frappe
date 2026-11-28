<template>
	<!-- its list hangs under it, over the composer; rows a menu's height, a chat's title each -->
	<span class="relative z-20">
		<Button
			ref="trigger"
			variant="ghost"
			icon="lucide-history"
			:class="open ? 'bg-surface-gray-2' : ''"
			:title="__('Recent chats')"
			:aria-expanded="open"
			@click="open ? close() : show()"
		/>
		<PalettePanel
			v-if="open"
			:title="__('Recent chats')"
			dropdown
			below
			:width="layout.narrow ? 264 : 360"
			:query="search"
			:busy="flow.state.sessionsLoading"
			@close="close"
		>
			<div class="flex flex-none pl-1 pr-2.5 pt-1">
				<input
					ref="field"
					v-model="search"
					:placeholder="__('Search chats…')"
					:aria-label="__('Search chats')"
					spellcheck="false"
					class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-base text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
				/>
			</div>
			<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
				<button
					v-for="s in rows"
					:key="s.session_id"
					data-palette-item
					:aria-current="s.session_id === flow.state.sessionId ? 'true' : undefined"
					class="flow-palette-row !min-h-7"
					@click="choose(s.session_id)"
				>
					<span class="min-w-0 truncate">{{ flow.sessionTitle(s) }}</span>
					<span v-if="s.session_id === flow.state.sessionId" class="lucide-check ml-auto size-4 flex-none" aria-hidden="true" />
				</button>
				<div v-if="!rows.length" class="flow-palette-empty">{{ empty }}</div>
				<button
					v-if="flow.state.sessionsMore"
					data-palette-item
					class="flow-palette-row"
					:disabled="flow.state.sessionsLoading"
					@click="flow.loadMoreSessions()"
				>
					<span class="flow-palette-hint">{{ flow.state.sessionsLoading ? __("Loading more…") : __("Load more") }}</span>
				</button>
			</div>
		</PalettePanel>
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue"
import { Button } from "frappe-ui/src/components/Button"

import { useDebouncedValue } from "../debounce.js"
import { layout } from "../layout.js"
import { __ } from "../translate.js"
import PalettePanel from "./PalettePanel.vue"

// The chats, under a clock in a header with no sidebar beside it: the sidebar's list and search
const flow = inject("flow")
const open = ref(false)
const search = ref("")
const field = ref(null)
// past a full page the host searches too, as it does for the sidebar's box
watch(useDebouncedValue(search, 150), (q) => flow.searchSessions(q))

const rows = computed(() => {
	const q = search.value.trim().toLowerCase()
	return flow.state.sessions.filter((session) => !q || flow.sessionTitle(session).toLowerCase().includes(q))
})
const empty = computed(() => {
	if (flow.state.sessionsLoading) return __("Loading…")
	return search.value ? __("No matching chats") : __("No chats yet")
})

function show() {
	open.value = true
	nextTick(() => field.value?.focus())
}

// a search left in the box gives way to the whole list; the keyboard goes back to the clock
const trigger = ref(null)
function close(refocus = true) {
	open.value = false
	search.value = ""
	if (refocus) nextTick(() => trigger.value?.$el?.focus())
}

function choose(id) {
	close(false)
	if (id !== flow.state.sessionId) flow.openSession(id)
}
</script>
