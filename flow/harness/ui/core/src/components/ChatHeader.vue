<template>
	<header class="flex flex-none items-center gap-2 border-b border-outline-gray-1 px-3 py-2">
		<template v-if="!sidebarOpen">
			<button class="flow-icon-btn" title="Show sidebar" @click="emit('open-sidebar')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
			<button class="flow-icon-btn" title="New chat" @click="flow.startNewChat()">
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
			</button>
		</template>

		<span class="min-w-0 truncate text-sm font-medium text-ink-gray-8" :title="title">{{ title }}</span>

		<span class="min-w-2 flex-1" />

		<span class="flex flex-none items-center gap-6">
			<span
				v-if="cwd"
				class="flex min-w-0 max-w-[260px] items-center gap-1.5 text-xs text-ink-gray-5"
				:title="cwd"
			>
				<FeatherIcon name="folder" class="h-3.5 w-3.5 flex-none" />
				<span class="truncate">{{ cwdName }}</span>
			</span>

			<span
				v-if="contextTokens > 0 || usedTokens > 0"
				class="flex items-center gap-2 whitespace-nowrap text-xs font-normal tabular-nums text-ink-gray-5"
			>
				<span v-if="contextWindow && contextTokens > 0" class="flex items-center gap-1.5" title="Context used">
					<span class="h-1 w-10 flex-none overflow-hidden rounded-full bg-surface-gray-3">
						<span
							class="block h-full rounded-full bg-surface-gray-6"
							:style="{ width: Math.min(100, (contextTokens / contextWindow) * 100) + '%' }"
						/>
					</span>
					<span>{{ formatTokens(contextTokens) }} / {{ formatTokens(contextWindow) }}</span>
				</span>
				<span v-else-if="usedTokens > 0" title="Tokens used">{{ formatTokens(usedTokens) }} tokens</span>
				<span v-if="cost > 0" class="flex items-center gap-2 text-ink-gray-4">
					<span aria-hidden="true" class="text-ink-gray-3">·</span>
					<span>${{ cost.toFixed(cost < 1 ? 3 : 2) }}</span>
				</span>
			</span>

			<button class="flow-icon-btn" title="Toggle theme" @click="toggleTheme">
				<FeatherIcon :name="theme === 'dark' ? 'moon' : 'sun'" class="h-3.5 w-3.5" />
			</button>
		</span>
	</header>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { conversationTitle, formatTokens } from "../transcript.js"

defineProps({ sidebarOpen: { type: Boolean, default: true } })
const emit = defineEmits(["open-sidebar"])
const flow = inject("flow")

// "." is the daemon-side default, not a path worth rendering. Before the first
// message there is no session yet — show the folder new chats will start in.
const cwd = computed(() => {
	const raw = flow.state.sessionId ? flow.state.session?.config?.cwd : flow.state.prefs.cwd
	return raw && raw !== "." ? raw : null
})

// no folder to show: fall back to the session's title, or "New chat"
const title = computed(() => {
	if (!flow.state.sessionId) return "New chat"
	return flow.state.session?.title ?? conversationTitle(flow.state.conversation) ?? "New chat"
})
const cwdName = computed(() => (cwd.value ?? "").split("/").filter(Boolean).pop() ?? "")

const usedTokens = computed(
	() => flow.state.conversation.usage.input + flow.state.conversation.usage.output,
)
const cost = computed(() => flow.state.conversation.usage.cost)
const contextTokens = computed(() => flow.state.conversation.contextTokens ?? 0)
const contextWindow = computed(() => flow.state.conversation.contextWindow ?? null)

const theme = computed(() => flow.state.prefs.theme)
function toggleTheme() {
	flow.setTheme(theme.value === "dark" ? "light" : "dark")
}
</script>
