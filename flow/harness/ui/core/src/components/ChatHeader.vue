<template>
	<header
		class="flex h-11 flex-none items-center gap-2 border-b px-3"
		:class="started ? 'border-outline-gray-1' : 'border-transparent'"
	>
		<template v-if="!sidebarOpen">
			<button class="flow-icon-btn" title="Show sidebar" @click="emit('open-sidebar')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
			<button class="flow-icon-btn" title="New chat" @click="flow.startNewChat()">
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
			</button>
		</template>

		<!-- the crumb (the folder, or the host's own) and the cost yield to the title on phones; a new
		     chat shows no crumb, title or line under them until its first message goes out -->
		<div v-if="started" class="flex min-w-0 items-center gap-2" :title="headerTitle">
			<span v-if="lead" class="hidden min-w-0 flex-none items-center gap-1.5 text-sm text-ink-gray-5 sm:flex">
				<FeatherIcon :name="lead.icon" class="h-3.5 w-3.5 flex-none" />
				<span class="max-w-[220px] truncate">{{ lead.label }}</span>
			</span>
			<span v-if="lead" aria-hidden="true" class="hidden flex-none text-sm text-ink-gray-3 sm:inline">/</span>
			<span class="min-w-0 truncate text-sm font-medium text-ink-gray-9">{{ title }}</span>
		</div>

		<span class="min-w-2 flex-1" />

		<span class="mr-1 flex flex-none items-center gap-3">
			<!-- the readout opens the transcript: the same totals, step by step. A narrow frame keeps
			     the bar, or the bare count, for the title's room, at a finger's height -->
			<button
				v-if="contextTokens > 0 || spent > 0"
				class="flex items-center gap-2 whitespace-nowrap rounded-4 px-1.5 py-1 text-xs font-normal tabular-nums text-ink-gray-5 hover:bg-surface-gray-2 max-md:h-7"
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
					<span class="max-md:hidden">{{ formatTokens(contextTokens) }} / {{ formatTokens(contextWindow) }}</span>
				</span>
				<span v-else-if="contextTokens > 0" title="Current context">
					{{ formatTokens(contextTokens) }}<span class="max-md:hidden"> in context</span>
				</span>
				<!-- a model switch drops the context reading; the session's spend stands in -->
				<span v-else title="Tokens used so far">{{ formatTokens(spent) }}<span class="max-md:hidden"> used</span></span>
				<span v-if="cost > 0" class="hidden items-center gap-2 text-ink-gray-4 sm:flex">
					<span aria-hidden="true" class="text-ink-gray-3">·</span>
					<span>${{ cost.toFixed(cost < 1 ? 3 : 2) }}</span>
				</span>
			</button>

			<ChatMenu v-if="menu" :session-id="flow.state.sessionId" :title="title" :actions="actions">
				<button class="flow-icon-btn" title="Chat options">
					<FeatherIcon name="more-horizontal" class="h-4 w-4" />
				</button>
			</ChatMenu>
			<button
				v-if="workspace && !workspaceOpen"
				class="flow-icon-btn"
				title="Open panel"
				@click="flow.setWorkspaceOpen(true)"
			>
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5 -scale-x-100" />
			</button>
		</span>
	</header>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { conversationTitle, formatTokens } from "../transcript.js"
import ChatMenu from "./ChatMenu.vue"

const props = defineProps({
	sidebarOpen: { type: Boolean, default: true },
	workspace: { type: Boolean, default: true }, // false: the host mounts no file panel
	actions: { type: Array, default: () => [] }, // the host's items atop the chat menu
	crumb: { type: Object, default: null }, // the host's { icon, label } before the title, in the folder's place
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
	() => props.crumb ?? (cwd.value ? { icon: "folder", label: flow.folderName(keptFolder.value ?? cwd.value), path: cwd.value } : null),
)

const headerTitle = computed(() => (lead.value ? `${lead.value.path ?? lead.value.label} / ${title.value}` : title.value))

const cost = computed(() => flow.state.conversation.usage.cost)
const spent = computed(() => {
	const { input, output } = flow.state.conversation.usage
	return input + output
})
const contextTokens = computed(() => flow.state.conversation.contextTokens ?? 0)
const contextWindow = computed(() => flow.state.conversation.contextWindow ?? null)

const workspaceOpen = computed(() => flow.state.workspace.open)
</script>
