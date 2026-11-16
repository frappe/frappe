<template>
	<!-- the chats are matched here, by their titles, so the palette leaves its own filter off -->
	<CommandPalette
		:open="open"
		:query="query"
		:filterable="false"
		:title="__('Search chats')"
		@update:open="emit('update:open', $event)"
		@update:query="query = $event"
		@select="choose"
	>
		<!-- the card's own colour, not frappe-ui's transparent: Chrome repaints an unfocused window's
		     field alone, and a transparent one shows the page through it as a dark strip. Held 1px
		     down so it doesn't cover the card's lit top edge. -->
		<CommandPaletteInput :placeholder="__('Search chats')" class="mt-px !bg-surface-elevation-1 !pt-[11px]" />
		<CommandPaletteList>
			<!-- held off the field's rule as far as the rows sit from the sides; a group brings its own -->
			<div v-if="!query.trim()" class="pt-2.5">
				<CommandPaletteItem value="new" :class="ROW">
					<template #prefix><span class="lucide-square-pen mr-2.5 size-4 flex-none text-ink-gray-6" aria-hidden="true" /></template>
					{{ __("New chat") }}
				</CommandPaletteItem>
			</div>
			<CommandPaletteGroup :label="query.trim() ? __('Chats') : __('Recent')">
				<CommandPaletteItem v-for="s in chats" :key="s.session_id" :value="s.session_id" :class="ROW">
					<template #prefix><span class="lucide-message-circle mr-2.5 size-4 flex-none text-ink-gray-6" aria-hidden="true" /></template>
					{{ flow.sessionTitle(s) }}
				</CommandPaletteItem>
			</CommandPaletteGroup>
		</CommandPaletteList>
		<CommandPaletteEmpty>{{ __("No chats match") }}</CommandPaletteEmpty>
	</CommandPalette>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import {
	CommandPalette,
	CommandPaletteEmpty,
	CommandPaletteGroup,
	CommandPaletteInput,
	CommandPaletteItem,
	CommandPaletteList,
} from "frappe-ui/experimental"

import { useDebouncedValue } from "../debounce.js"
import { __ } from "../translate.js"

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(["update:open", "new", "pick"])
const flow = inject("flow")
// a row in the chat's regular weight, as the sidebar lists the same titles; frappe-ui's is medium
const ROW = "!text-base !leading-tighter"

const query = ref("")
watch(() => props.open, (open) => open || (query.value = ""))

// past a page of chats the host matches the rest; only the newest query's answer lands
const found = ref([])
const debounced = useDebouncedValue(query, 150)
watch(debounced, async (q) => {
	const rows = q.trim() ? await flow.findSessions(q.trim()) : []
	if (q === debounced.value) found.value = rows
})

// matched as the query is typed, so the palette's first row is ready for Enter
const chats = computed(() => {
	const q = query.value.trim().toLowerCase()
	const loaded = new Set(flow.state.sessions.map((s) => s.session_id))
	return [...flow.state.sessions, ...found.value.filter((s) => !loaded.has(s.session_id))]
		.filter((s) => !q || flow.sessionTitle(s).toLowerCase().includes(q))
		.slice(0, 20)
})

function choose(value) {
	if (value === "new") emit("new")
	else emit("pick", chats.value.find((s) => s.session_id === value))
}
</script>
