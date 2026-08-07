<template>
	<Transition name="flow-backdrop">
		<button
			v-if="open"
			class="fixed inset-0 z-20 bg-black/30 md:hidden"
			aria-label="Close sidebar"
			@click="emit('close')"
		/>
	</Transition>
	<aside
		class="fixed inset-y-0 left-0 z-30 flex w-64 flex-none flex-col border-r border-outline-gray-1 bg-surface-menu-bar md:static"
		:class="[
			ready ? 'transition-[transform,margin-left] duration-200 ease-in-out' : '',
			open ? 'translate-x-0' : '-translate-x-full md:-ml-64 md:translate-x-0',
		]"
	>
		<div class="flex h-12 items-center gap-2.5 px-3.5">
			<BrandMark :size="22" />
			<span class="text-sm font-semibold text-ink-gray-9">Flow</span>
			<span class="flex-1" />
			<button class="flow-icon-btn" title="Hide sidebar" @click="emit('close')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
		</div>

		<div class="px-2.5 pb-1.5">
			<button
				class="flex h-9 w-full items-center gap-2 rounded-lg px-2.5 text-xs font-medium text-ink-gray-8 transition-colors hover:bg-surface-gray-2"
				@click="flow.startNewChat()"
			>
				<FeatherIcon name="plus" class="h-4 w-4 text-ink-gray-6" />
				New chat
			</button>
		</div>

		<div class="px-2.5 pb-1.5">
			<div
				class="flex h-8 items-center gap-2 rounded-md border border-outline-gray-2 bg-surface-white px-2 text-ink-gray-5 transition-colors focus-within:border-outline-gray-3"
			>
				<FeatherIcon name="search" class="h-3.5 w-3.5 flex-none" />
				<input
					v-model="query"
					placeholder="Search chats"
					spellcheck="false"
					class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
				/>
				<button
					v-if="query"
					class="grid h-4 w-4 flex-none place-items-center rounded text-ink-gray-4 hover:text-ink-gray-8"
					title="Clear"
					@click="query = ''"
				>
					<FeatherIcon name="x" class="h-3 w-3" />
				</button>
			</div>
		</div>

		<div class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2.5 pb-2.5">
			<div
				v-if="filtered.length"
				class="px-2.5 pb-1 pt-3 text-2xs font-medium text-ink-gray-5"
			>
				Recent sessions
			</div>
			<div
				v-for="s in filtered"
				:key="s.session_id"
				role="button"
				tabindex="0"
				class="group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2 focus-visible:outline-none"
				:class="s.session_id === flow.state.sessionId ? 'bg-surface-gray-3' : ''"
				@click="flow.openSession(s.session_id)"
				@keydown.enter.prevent="flow.openSession(s.session_id)"
				@keydown.space.prevent="flow.openSession(s.session_id)"
			>
				<span
					class="min-w-0 flex-1 truncate text-xs leading-snug"
					:class="s.session_id === flow.state.sessionId ? 'font-medium text-ink-gray-9' : 'text-ink-gray-8'"
				>
					{{ flow.sessionTitle(s) }}
				</span>
				<!-- dot and delete share one fixed slot; only opacity swaps, so the
				     row never reflows on hover -->
				<span class="relative h-5 w-5 flex-none">
					<span
						class="absolute inset-0 grid place-items-center text-2xs text-ink-gray-5 group-hover:opacity-0"
					>
						<span
							v-if="s.state === 'running'"
							class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-surface-green-3"
							title="Running"
						/>
						<span v-else-if="s.state === 'paused'" title="Waiting for approval">⏸</span>
					</span>
					<button
						class="absolute inset-0 grid place-items-center rounded-[5px] text-ink-gray-5 opacity-0 hover:bg-surface-gray-4 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
						title="Delete session"
						@click.stop="confirmDelete(s)"
						@keydown.enter.stop
						@keydown.space.stop
					>
						<FeatherIcon name="trash-2" class="h-[13px] w-[13px]" />
					</button>
				</span>
			</div>
			<div v-if="filtered.length === 0" class="px-2.5 py-8 text-center text-xs text-ink-gray-5">
				{{ query ? "No matches." : "No chats yet — start one." }}
			</div>
		</div>

		<footer class="flex min-h-[44px] items-center gap-2 border-t border-outline-gray-1 px-3.5 py-2">
			<span class="h-1.5 w-1.5 flex-none rounded-full bg-surface-green-3" />
			<span class="min-w-0 flex-1 truncate text-2xs text-ink-gray-5" :title="daemonUrl">
				{{ daemonUrl }}
			</span>
			<button
				class="flex-none rounded p-1 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-7"
				title="Refresh sessions"
				@click="flow.refreshSessions()"
			>
				<FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" />
			</button>
		</footer>
	</aside>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { dialog } from "frappe-ui/src/utils/dialog"

import { useDebouncedValue } from "../debounce.js"
import BrandMark from "./BrandMark.vue"

const props = defineProps({ open: { type: Boolean, default: true } })
const emit = defineEmits(["close"])
const flow = inject("flow")

const query = ref("")
const debouncedQuery = useDebouncedValue(query, 150)

// dialog.confirm, not dialog.danger: danger's red theme injects a header
// icon; the destructive styling lives on the action button instead
function confirmDelete(s) {
	dialog.confirm({
		title: "Delete chat?",
		message: `“${flow.sessionTitle(s)}” and its full history will be permanently removed.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: () => flow.deleteSession(s.session_id),
			},
		],
	})
}

// enable the slide transition only after mount, so a closed saved state
// doesn't animate on page load
const ready = ref(false)
onMounted(() => requestAnimationFrame(() => (ready.value = true)))

const filtered = computed(() => {
	const q = debouncedQuery.value.trim().toLowerCase()
	if (!q) return flow.state.sessions
	return flow.state.sessions.filter((s) => flow.sessionTitle(s).toLowerCase().includes(q))
})

const daemonUrl = computed(() => {
	const base = flow.client.baseUrl?.replace(/^https?:\/\//, "")
	return base || window.location.host
})
</script>

<style scoped>
.flow-backdrop-enter-active,
.flow-backdrop-leave-active {
	transition: opacity 0.2s ease;
}
.flow-backdrop-enter-from,
.flow-backdrop-leave-to {
	opacity: 0;
}
</style>
