<template>
	<!-- the chats are matched here, by their titles, so the palette leaves its own filter off -->
	<CommandPalette
		:open="open"
		:query="query"
		:filterable="false"
		title="Search chats"
		@update:open="emit('update:open', $event)"
		@update:query="emit('update:query', $event)"
		@select="choose"
	>
		<!-- the card's own colour, not frappe-ui's transparent: Chrome repaints an unfocused window's
		     field alone, and a transparent one shows the page through it as a dark strip -->
		<CommandPaletteInput placeholder="Search chats" class="!bg-surface-elevation-1" />
		<CommandPaletteList>
			<!-- held off the field's rule as far as the rows sit from the sides; a group brings its own -->
			<div v-if="!query.trim()" class="pt-2.5">
				<CommandPaletteItem value="new">
					<template #prefix><span class="lucide-square-pen mr-2.5 size-4 flex-none text-ink-gray-6" aria-hidden="true" /></template>
					New chat
				</CommandPaletteItem>
			</div>
			<CommandPaletteGroup :label="query.trim() ? 'Chats' : 'Recent'">
				<CommandPaletteItem v-for="s in chats" :key="s.session_id" :value="s.session_id">
					<template #prefix><span class="lucide-message-circle mr-2.5 size-4 flex-none text-ink-gray-6" aria-hidden="true" /></template>
					{{ flow.sessionTitle(s) }}
				</CommandPaletteItem>
			</CommandPaletteGroup>
		</CommandPaletteList>
		<CommandPaletteEmpty>No chats match</CommandPaletteEmpty>
	</CommandPalette>
</template>

<script setup>
import { computed, inject } from "vue"
import {
	CommandPalette,
	CommandPaletteEmpty,
	CommandPaletteGroup,
	CommandPaletteInput,
	CommandPaletteItem,
	CommandPaletteList,
} from "frappe-ui/experimental"

const props = defineProps({
	open: { type: Boolean, default: false },
	query: { type: String, default: "" },
})
const emit = defineEmits(["update:open", "update:query", "new", "pick"])
const flow = inject("flow")

// matched as the query is typed, so the palette's first row is ready for Enter; past a page of chats
// the sidebar's search reloads them from the server
const chats = computed(() => {
	const q = props.query.trim().toLowerCase()
	return flow.state.sessions.filter((s) => !q || flow.sessionTitle(s).toLowerCase().includes(q)).slice(0, 20)
})

function choose(value) {
	if (value === "new") emit("new")
	else emit("pick", chats.value.find((s) => s.session_id === value))
}
</script>
