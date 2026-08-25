<template>
	<div class="relative min-h-0 flex-1">
	<div
		ref="scroller"
		class="h-full overflow-y-auto px-5"
		:style="{ scrollPaddingBottom: composerHeight + 24 + 'px' }"
		@scroll="onScroll"
	>
		<!-- pad by the floating composer's height so "center" means the visible
		     area above it, not the full page -->
		<div
			v-if="empty"
			class="flex h-full flex-col items-center justify-center gap-5 text-center"
			:style="{ paddingBottom: composerHeight + 'px' }"
		>
			<BrandMark :size="48" />
			<h2 class="text-3xl font-normal text-ink-gray-9">What would you like to build?</h2>
		</div>
		<div
			v-else
			class="flow-thread mx-auto flex max-w-[800px] flex-col gap-5 pt-4"
			:style="{ paddingBottom: composerHeight + 40 + 'px' }"
		>
			<template v-for="(item, i) in items" :key="item.key">
				<UserBubble v-if="item.kind === 'user'" :entry="item.entry" />
				<TurnFold
					v-else-if="item.kind === 'turn-fold'"
					:label="item.label"
					:expanded="item.expanded"
					@toggle="toggleTurn(item.turnKey)"
				/>
				<AssistantText v-else-if="item.kind === 'text'" :block="item.block" />
				<ThinkingBlock v-else-if="item.kind === 'thinking'" :block="item.block" :live="item.live" />
				<ToolGroup
					v-else-if="item.kind === 'group'"
					:steps="item.steps"
					:sealed="i < items.length - 1 || !conversation.running"
					:live-label="conversation.liveLabel"
				/>
				<!-- the latest turn's copy button stays visible; older ones hover-reveal -->
				<div
					v-else-if="item.kind === 'turn-copy'"
					class="-mt-3 flex items-center gap-2"
					:class="i === lastTurnCopyIndex ? '' : 'flow-turn-copy'"
				>
					<CopyButton
						:text="item.text"
						title="Copy response"
						class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					/>
					<span v-if="formatTime(item.ts)" class="text-2xs text-ink-gray-4">{{ formatTime(item.ts) }}</span>
				</div>
				<ApprovalCard v-else-if="item.kind === 'approval'" :calls="item.calls" :seq="item.seq" />
				<div
					v-else-if="item.kind === 'compaction'"
					class="flex items-center gap-2.5 text-sm text-ink-gray-5"
				>
					<FeatherIcon name="archive" class="h-3.5 w-3.5 flex-none" />
					<span>Context compacted ({{ item.entry.reason }})</span>
				</div>
				<div
					v-else-if="item.kind === 'notice'"
					class="flex items-center gap-3 py-1 text-2xs text-ink-gray-4"
				>
					<span class="h-px flex-1 bg-surface-gray-3" />
					<span>{{ item.text }}</span>
					<span class="h-px flex-1 bg-surface-gray-3" />
				</div>
				<div
					v-else-if="item.kind === 'error'"
					class="rounded-lg border border-outline-red-1 bg-surface-red-1 px-3.5 py-2.5 text-sm text-ink-red-3"
				>
					{{ item.error.message }}
				</div>
			</template>

			<!-- Before the first streamed block (or during retry/compaction), no
			     transcript item owns the live status, so render one fallback line. -->
			<div v-if="showStandaloneStatus" class="text-sm font-medium">
				<span class="flow-shimmer">{{ conversation.liveLabel }}</span>
			</div>

		</div>
	</div>

	<button
		v-if="!stick && !empty"
		class="absolute left-1/2 z-10 grid h-8 w-8 -translate-x-1/2 place-items-center rounded-full border border-outline-gray-2 bg-surface-white text-ink-gray-6 shadow-md hover:text-ink-gray-9"
		:style="{ bottom: composerHeight + 12 + 'px' }"
		title="Scroll to bottom"
		@click="toBottom"
	>
		<FeatherIcon name="arrow-down" class="h-4 w-4" />
	</button>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { buildItems, formatTime } from "../transcript.js"
import ApprovalCard from "./ApprovalCard.vue"
import AssistantText from "./AssistantText.vue"
import BrandMark from "./BrandMark.vue"
import CopyButton from "./CopyButton.vue"
import ThinkingBlock from "./ThinkingBlock.vue"
import ToolGroup from "./ToolGroup.vue"
import TurnFold from "./TurnFold.vue"
import UserBubble from "./UserBubble.vue"

const flow = inject("flow")
const conversation = computed(() => flow.state.conversation)
const expandedTurnKeys = ref(new Set())
const items = computed(() => buildItems(conversation.value, expandedTurnKeys.value))

const empty = computed(() => !flow.state.sessionId && !flow.state.loading)
const composerHeight = inject("composerHeight", ref(120))
const lastTurnCopyIndex = computed(() =>
	items.value.findLastIndex((item) => item.kind === "turn-copy"),
)
const lastItem = computed(() => items.value[items.value.length - 1])
// Streamed thinking and tool groups render their own status. The fallback is
// reserved for statuses that have no preview item yet.
const lastIsOpenGroup = computed(
	() => conversation.value.running && lastItem.value?.kind === "group",
)
const lastIsLiveThinking = computed(
	() => lastItem.value?.kind === "thinking" && lastItem.value.live,
)
const showStandaloneStatus = computed(
	() =>
		!!conversation.value.liveLabel &&
		!lastIsOpenGroup.value &&
		!lastIsLiveThinking.value,
)

const partialVersion = computed(() => {
	const partial = conversation.value.partial
	const tail = partial[partial.length - 1]
	const streamedLength = tail?.text?.length ?? tail?.thinking?.length ?? 0
	return `${partial.length}:${tail?.type ?? ""}:${tail?.id ?? ""}:${tail?.name ?? ""}:${streamedLength}`
})

const scroller = ref(null)
const stick = ref(true)
let lastScrollTop = 0

function onScroll() {
	const el = scroller.value
	if (!el) return
	const distance = el.scrollHeight - el.scrollTop - el.clientHeight
	const goingUp = el.scrollTop < lastScrollTop
	lastScrollTop = el.scrollTop
	// any upward scroll unsticks; only scrolling down near the bottom re-sticks
	if (distance < 1) stick.value = true
	else if (goingUp) stick.value = false
	else stick.value = distance < 80
}

function toBottom() {
	const el = scroller.value
	if (!el) return
	el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
	stick.value = true
}

function toggleTurn(turnKey) {
	const next = new Set(expandedTurnKeys.value)
	if (next.has(turnKey)) next.delete(turnKey)
	else next.add(turnKey)
	expandedTurnKeys.value = next
}

watch(
	() => [
		conversation.value.entries.length,
		partialVersion.value,
		conversation.value.liveLabel,
		conversation.value.running,
		composerHeight.value,
	],
	async () => {
		if (!stick.value) return
		await nextTick()
		const el = scroller.value
		if (el) el.scrollTop = el.scrollHeight
	},
)

watch(
	() => flow.state.sessionId,
	() => {
		stick.value = true
		expandedTurnKeys.value = new Set()
	},
)
</script>
