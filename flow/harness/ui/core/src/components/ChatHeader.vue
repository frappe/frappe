<template>
	<header class="flex h-11 flex-none items-center gap-2 border-b border-outline-gray-1 px-3">
		<template v-if="!sidebarOpen">
			<button class="flow-icon-btn" title="Show sidebar" @click="emit('open-sidebar')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
			<button class="flow-icon-btn" title="New chat" @click="flow.startNewChat()">
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
			</button>
		</template>

		<!-- the folder crumb and the cost yield to the title on phones -->
		<div class="flex min-w-0 items-center gap-2" :title="headerTitle">
			<!-- before the first message the crumb is a button: pick the folder the chat starts in -->
			<component
				:is="flow.state.sessionId ? 'span' : 'button'"
				v-if="cwd"
				class="hidden min-w-0 flex-none items-center gap-1.5 text-sm text-ink-gray-5 sm:flex"
				:class="!flow.state.sessionId && 'rounded-4 px-1.5 py-1 hover:bg-surface-gray-2 hover:text-ink-gray-8'"
				:title="flow.state.sessionId ? undefined : 'Change working directory'"
				@click="!flow.state.sessionId && chooseFolder()"
			>
				<FeatherIcon name="folder" class="h-3.5 w-3.5 flex-none" />
				<span class="max-w-[220px] truncate">{{ cwdName }}</span>
			</component>
			<span v-if="cwd" aria-hidden="true" class="hidden flex-none text-sm text-ink-gray-3 sm:inline">/</span>
			<span class="min-w-0 truncate text-sm font-medium text-ink-gray-9">{{ title }}</span>
		</div>

		<span class="min-w-2 flex-1" />

		<span class="flex flex-none items-center gap-6">
			<!-- the readout opens the transcript: the same totals, step by step -->
			<button
				v-if="contextTokens > 0 || spent > 0"
				class="flex items-center gap-2 whitespace-nowrap rounded-4 px-1.5 py-1 text-xs font-normal tabular-nums text-ink-gray-5 hover:bg-surface-gray-2"
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
				<span v-else-if="contextTokens > 0" title="Current context">
					{{ formatTokens(contextTokens) }} in context
				</span>
				<!-- a model switch drops the context reading; the session's spend stands in -->
				<span v-else title="Tokens used so far">{{ formatTokens(spent) }} used</span>
				<span v-if="cost > 0" class="hidden items-center gap-2 text-ink-gray-4 sm:flex">
					<span aria-hidden="true" class="text-ink-gray-3">·</span>
					<span>${{ cost.toFixed(cost < 1 ? 3 : 2) }}</span>
				</span>
			</button>

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

defineProps({
	sidebarOpen: { type: Boolean, default: true },
	workspace: { type: Boolean, default: true }, // false: the host mounts no file panel
})
const emit = defineEmits(["open-sidebar"])
const flow = inject("flow")

// "." is the daemon-side default, not a path worth rendering. Before the first
// message there is no session yet — show the folder new chats will start in.
const cwd = computed(() => {
	const raw = flow.state.sessionId ? flow.state.session?.config?.cwd : flow.state.prefs.cwd
	return raw && raw !== "." ? raw : null
})

// no folder to show: fall back to the session's title, or "New chat" (nothing while a chat loads)
const title = computed(
	() =>
		flow.state.session?.title ?? conversationTitle(flow.state.conversation) ?? (flow.state.loading ? "" : "New chat"),
)
const cwdName = computed(() => (cwd.value ?? "").split("/").filter(Boolean).pop() ?? "")

async function chooseFolder() {
	const path = await flow.pickFolder()
	if (!path) return
	// a session restored while the picker was open: the pick still opens a new chat
	if (flow.state.sessionId) flow.startNewChat({ cwd: path })
	else flow.setCwd(path)
}
const headerTitle = computed(() => (cwd.value ? `${cwd.value} / ${title.value}` : title.value))

const cost = computed(() => flow.state.conversation.usage.cost)
const spent = computed(() => {
	const { input, output } = flow.state.conversation.usage
	return input + output
})
const contextTokens = computed(() => flow.state.conversation.contextTokens ?? 0)
const contextWindow = computed(() => flow.state.conversation.contextWindow ?? null)

const workspaceOpen = computed(() => flow.state.workspace.open)
</script>
