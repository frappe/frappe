<template>
	<!-- touch has no hover: there the button opens the drawer, as before -->
	<slot v-if="layout.phone" />
	<HoverCard
		v-else
		v-model:open="open"
		side="bottom"
		align="start"
		:offset="6"
		:hover-delay="150"
		:leave-delay="200"
	>
		<template #trigger><slot /></template>
		<!-- the sidebar's essentials and recent chats, floating: a chat changes without the page's
		     layout changing. A click on the button still opens the sidebar for good -->
		<div class="flex w-60 flex-col gap-2 p-1.5">
			<div class="flex items-center gap-2 px-2 py-1.5">
				<BrandMark line :size="16" class="!text-ink-gray-6" />
				<span class="text-base font-medium text-ink-gray-6">Flow</span>
			</div>
			<div class="flex flex-col gap-px">
				<button v-for="item in items" :key="item.label" type="button" :class="ROW" @click="run(item.onClick)">
					<span :class="[item.icon, 'size-4 flex-none']" aria-hidden="true" />
					<span class="min-w-0 flex-1 truncate text-left">{{ item.label }}</span>
					<KeyboardShortcut v-if="item.combo" :combo="item.combo" class="flex-none" />
				</button>
			</div>
			<div v-if="recent.length" class="flex flex-col gap-px">
				<p class="flex h-7 items-center px-2 text-sm font-medium text-ink-gray-4">Chat</p>
				<button
					v-for="s in recent"
					:key="s.session_id"
					type="button"
					:class="[ROW, s.session_id === flow.state.sessionId && 'bg-surface-alpha-gray-2 text-ink-gray-9']"
					@click="run(() => pick(s))"
				>
					<span class="min-w-0 flex-1 truncate text-left">{{ flow.sessionTitle(s) }}</span>
				</button>
			</div>
		</div>
	</HoverCard>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import HoverCard from "frappe-ui/src/components/HoverCard/HoverCard.vue"
import KeyboardShortcut from "frappe-ui/src/components/KeyboardShortcut/KeyboardShortcut.vue"

import { layout } from "../layout.js"
import BrandMark from "./BrandMark.vue"

// The sidebar while it's hidden: hovering its button floats the essentials and the latest chats
// beside it, so a chat can change without the sidebar taking its room back.
const props = defineProps({
	menu: { type: Array, default: () => [] }, // the host's items in the app menu, after Settings
	beforeSwitch: { type: Function, default: null }, // a host's say before the open chat changes
})
const flow = inject("flow")
const open = ref(false)

const RECENT = 8
const recent = computed(() => flow.state.sessions.slice(0, RECENT))

const items = computed(() => [
	{ label: "New chat", icon: "lucide-plus", combo: "Mod+Shift+O", onClick: () => switchTo(() => flow.startNewChat()) },
	// the sidebar owns the search palette; it opens over the page with the sidebar left hidden
	{ label: "Search", icon: "lucide-search", combo: "Mod+K", onClick: () => window.dispatchEvent(new CustomEvent("flow-search")) },
	{ label: "Settings", icon: "lucide-settings", onClick: () => flow.setSettingsOpen(true) },
	...props.menu,
])

function run(action) {
	open.value = false
	action?.()
}

async function switchTo(go) {
	if (props.beforeSwitch && !(await props.beforeSwitch())) return
	go()
}
const pick = (session) => switchTo(() => flow.openSession(session.session_id))

// an alpha fill, as frappe-ui's menus highlight: it shows on the raised panel in light and dark alike
const ROW =
	"flex h-7 flex-none items-center gap-1.5 rounded-4 px-2 text-base text-ink-gray-7 transition-colors hover:bg-surface-alpha-gray-2 hover:text-ink-gray-9 focus-visible:bg-surface-alpha-gray-2 focus-visible:outline-none"
</script>
