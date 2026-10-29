<template>
	<header
		class="flex flex-none items-center gap-2 border-b px-3"
		:class="
			besideNavbar
				? [
						'box-content border-gray-200 dark:border-outline-gray-1',
						besideNavbar === 'desk' ? 'h-12' : 'h-10.5',
					]
				: ['h-11', started ? 'border-outline-gray-1' : 'border-transparent']
		"
	>
		<template v-if="!sidebarOpen && !history">
			<button class="flow-icon-btn" title="Show sidebar" @click="emit('open-sidebar')">
				<span class="lucide-panel-left size-3.5" aria-hidden="true" />
			</button>
			<button v-if="started" class="flow-icon-btn" title="New chat" @click="flow.startNewChat()">
				<span class="lucide-plus size-3.5" aria-hidden="true" />
			</button>
		</template>

		<!-- the crumb (the folder, or the host's own) and the cost yield to the title on phones; a new
		     chat shows no crumb, title or line under them until its first message goes out -->
		<div v-if="started" class="flex min-w-0 items-center gap-2" :title="headerTitle">
			<span v-if="lead" class="hidden min-w-0 flex-none items-center gap-1.5 text-base text-ink-gray-5 sm:flex">
				<span class="size-3.5 flex-none" :class="lead.icon" aria-hidden="true" />
				<span class="max-w-[220px] truncate">{{ lead.label }}</span>
			</span>
			<span v-if="lead" aria-hidden="true" class="hidden flex-none text-base text-ink-gray-3 sm:inline">/</span>
			<span class="min-w-0 truncate text-base font-medium text-ink-gray-9">{{ title }}</span>
		</div>

		<ChatMenu
			v-if="menu || menuActions.length"
			:session-id="menu ? flow.state.sessionId : null"
			:title="title"
			:actions="menuActions"
			align="start"
		>
			<button class="flow-icon-btn flex-none" title="Chat options">
				<span class="lucide-ellipsis size-4" aria-hidden="true" />
			</button>
		</ChatMenu>

		<span class="min-w-2 flex-1" />

		<span class="mr-1 flex flex-none items-center gap-1">
			<!-- the readout opens the transcript: the same totals, step by step. A narrow frame leaves
			     the title the room: its chat menu opens the transcript instead -->
			<button
				v-if="transcript && !layout.narrow && (contextTokens > 0 || spent > 0)"
				class="mr-2 flex items-center gap-2 whitespace-nowrap rounded-4 px-1.5 py-1 text-sm font-normal tabular-nums text-ink-gray-5 hover:bg-surface-gray-2"
				title="Tokens, step by step"
				@click="flow.setTranscriptOpen(true)"
			>
				<span v-if="contextWindow && contextTokens > 0" class="flex items-center gap-1.5" title="Context used">
					<span class="h-1 w-10 flex-none overflow-hidden rounded-full bg-surface-gray-3">
						<span
							class="block h-full rounded-full bg-surface-gray-9"
							:style="{ width: Math.min(100, (contextTokens / contextWindow) * 100) + '%' }"
						/>
					</span>
					<span>{{ formatTokens(contextTokens) }} / {{ formatTokens(contextWindow) }}</span>
				</span>
				<span v-else-if="contextTokens > 0" title="Current context">{{ formatTokens(contextTokens) }} in context</span>
				<!-- a model switch drops the context reading; the session's spend stands in -->
				<span v-else title="Tokens used so far">{{ formatTokens(spent) }} used</span>
				<span v-if="cost > 0" class="flex items-center gap-2 text-ink-gray-4">
					<span aria-hidden="true" class="text-ink-gray-3">·</span>
					<span>${{ cost.toFixed(cost < 1 ? 3 : 2) }}</span>
				</span>
			</button>

			<ChatHistory v-if="history" />
			<button v-if="history && started" class="flow-icon-btn" title="New chat" @click="flow.startNewChat()">
				<span class="lucide-plus size-3.5" aria-hidden="true" />
			</button>
			<Dropdown v-if="history && manage" align="end" :options="manageOptions">
				<template #trigger>
					<button class="flow-icon-btn" title="Manage">
						<span class="lucide-settings size-3.5" aria-hidden="true" />
					</button>
				</template>
			</Dropdown>
			<button
				v-if="workspace && !workspaceOpen"
				class="flow-icon-btn ml-2"
				title="Open panel"
				@click="flow.setWorkspaceOpen(true)"
			>
				<span class="lucide-panel-left size-3.5 -scale-x-100" aria-hidden="true" />
			</button>
			<slot name="end" />
		</span>
	</header>
</template>

<script setup>
import { computed, inject } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"

import { layout } from "../layout.js"
import { conversationTitle, formatTokens } from "../transcript.js"
import ChatHistory from "./ChatHistory.vue"
import ChatMenu from "./ChatMenu.vue"

const props = defineProps({
	sidebarOpen: { type: Boolean, default: true },
	workspace: { type: Boolean, default: true }, // false: the host mounts no file panel
	actions: { type: Array, default: () => [] }, // the host's items atop the chat menu
	crumb: { type: Object, default: null }, // the host's { icon, label } before the title, in the folder's place
	// no sidebar beside it: a clock lists the chats, and a gear leads to `nav` and Settings
	history: { type: Boolean, default: false },
	nav: { type: Array, default: () => [] }, // the host's rows in the sidebar, like links to its pages
	manage: { type: Boolean, default: true }, // false: no gear, the host's page leads there itself
	// "desk" or "app", beside that page's head: as tall, and always ruled in its color, so the two
	// lines meet. Desk's head is 48px, a frappe-ui app's 42px
	besideNavbar: { type: String, default: null },
	transcript: { type: Boolean, default: true }, // false: no token readout or Transcript item
})
const emit = defineEmits(["open-sidebar"])
const flow = inject("flow")

// the open chat's menu, once it has loaded; a chat the user may only view has none
const menu = computed(() => Boolean(flow.state.sessionId && flow.state.session && !flow.state.session.read_only))

// a chat starts with its first message, before its session exists
const started = computed(() => Boolean(flow.state.sessionId || flow.state.conversation.sending.length))

// "." is the daemon-side default, not a path worth rendering. While the first message
// is out there is no session yet — show the folder the chat starts in.
const cwd = computed(() => {
	const raw = flow.state.sessionId ? flow.state.session?.config?.cwd : flow.state.prefs.cwd
	return raw && raw !== "." ? raw : null
})

// no folder to show: fall back to the session's title, or "New chat" (nothing while a chat loads)
const title = computed(
	() =>
		flow.state.session?.title ?? conversationTitle(flow.state.conversation) ?? (flow.state.loading ? "" : "New chat"),
)
// the open chat's folder as the sidebar keeps it, which names it even when reached through a link
const keptFolder = computed(() => flow.state.sessions.find((s) => s.session_id === flow.state.sessionId)?.workspace)
// before the title: the host's crumb, or the folder by its workspace's name, whose full path shows on hover
const lead = computed(
	() => props.crumb ?? (cwd.value ? { icon: "lucide-folder", label: flow.folderName(keptFolder.value ?? cwd.value), path: cwd.value } : null),
)

const headerTitle = computed(() => (lead.value ? `${lead.value.path ?? lead.value.label} / ${title.value}` : title.value))

const cost = computed(() => flow.state.conversation.usage.cost)
const spent = computed(() => {
	const { input, output } = flow.state.conversation.usage
	return input + output
})
const contextTokens = computed(() => flow.state.conversation.contextTokens ?? 0)
const contextWindow = computed(() => flow.state.conversation.contextWindow ?? null)

// a narrow frame's chat menu opens the transcript in the readout's place
const menuActions = computed(() => [
	...(props.transcript && layout.narrow && (contextTokens.value > 0 || spent.value > 0)
		? [{ label: "Transcript", icon: "lucide-list", onClick: () => flow.setTranscriptOpen(true) }]
		: []),
	...props.actions,
])
const manageOptions = computed(() => [
	...(props.nav.length ? [{ group: "nav", hideLabel: true, options: props.nav }] : []),
	{
		group: "settings",
		hideLabel: true,
		options: [{ label: "Settings", icon: "lucide-settings", onClick: () => flow.setSettingsOpen(true) }],
	},
])

const workspaceOpen = computed(() => flow.state.workspace.open)
</script>
