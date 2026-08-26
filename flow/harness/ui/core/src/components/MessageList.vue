<template>
	<div class="relative min-h-0 flex-1">
	<div
		ref="scroller"
		class="h-full overflow-y-auto"
		:class="prompts.length ? 'px-10' : 'px-5'"
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
				<UserBubble
					v-if="item.kind === 'user'"
					:entry="item.entry"
					:data-prompt-key="item.key"
					class="scroll-mt-3"
				/>
				<TurnFold
					v-else-if="item.kind === 'turn-fold'"
					:data-turn-fold="item.turnKey"
					:label="item.label"
					:expanded="item.expanded"
					@toggle="toggleTurn(item.turnKey)"
				/>
				<AssistantText v-else-if="item.kind === 'text'" :block="item.block" />
				<!-- like ToolGroup below: the row's own py-2.5 already pads it -->
				<ThinkingBlock
					v-else-if="item.kind === 'thinking'"
					:class="items[i - 1]?.kind === 'turn-fold' ? '-mt-3' : ''"
					:block="item.block"
					:live="item.live"
				/>
				<!-- the first row's own py-2.5 already pads it; offset the thread gap -->
				<ToolGroup
					v-else-if="item.kind === 'group'"
					:class="items[i - 1]?.kind === 'turn-fold' ? '-mt-3' : ''"
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
				<TurnFiles v-else-if="item.kind === 'turn-files'" class="flow-turn-files -mt-1" :files="item.files" />
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
			     transcript item owns the live status, so render one fallback line.
			     py-2.5 keeps it on the same rhythm as the rows that replace it; after
			     a thinking block the thread gap collapses too, so the status sits
			     exactly where the upcoming tool row will render. -->
			<div
				v-if="showStandaloneStatus"
				class="py-2.5 text-sm font-medium"
				:class="lastItem?.kind === 'thinking' ? '-mt-5' : ''"
			>
				<span class="flow-shimmer">{{ conversation.liveLabel }}</span>
			</div>

		</div>
	</div>

	<PromptRail
		v-if="prompts.length"
		:prompts="prompts"
		:active-key="activePromptKey"
		@select="scrollToPrompt"
	/>

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

import { buildItems, formatTime, userAttachments, userText } from "../transcript.js"
import ApprovalCard from "./ApprovalCard.vue"
import AssistantText from "./AssistantText.vue"
import BrandMark from "./BrandMark.vue"
import CopyButton from "./CopyButton.vue"
import PromptRail from "./PromptRail.vue"
import ThinkingBlock from "./ThinkingBlock.vue"
import ToolGroup from "./ToolGroup.vue"
import TurnFiles from "./TurnFiles.vue"
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
	// tool rows render on their display_ready upgrade (arguments landing), which
	// moves nothing else the autoscroller watches — count the upgraded calls
	const ready = partial.filter((b) => b.type === "tool_call" && b.arguments != null).length
	return `${partial.length}:${tail?.type ?? ""}:${tail?.id ?? ""}:${tail?.name ?? ""}:${streamedLength}:${ready}`
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
	// any upward scroll unsticks; scrolling down re-sticks only once the view
	// actually reaches the bottom — re-pinning from ~80px away yanks the page
	// out of the user's hands mid-scroll
	if (distance < 4) stick.value = true
	else if (goingUp) stick.value = false
	updateActivePrompt()
}

const prompts = computed(() =>
	items.value
		.filter((item) => item.kind === "user")
		.map((item) => {
			const text = userText(item.entry) || userAttachments(item.entry)[0]?.name || "Prompt"
			return { key: item.key, text: text.length > 400 ? text.slice(0, 400) + "…" : text }
		}),
)
const activePromptKey = ref(null)

// the active prompt is the last one that has scrolled past the upper third of
// the visible area — i.e. the turn currently being read
function updateActivePrompt() {
	const el = scroller.value
	if (!el || !prompts.value.length) {
		activePromptKey.value = null
		return
	}
	const threshold = el.getBoundingClientRect().top + el.clientHeight / 3
	let active = prompts.value[0].key
	for (const bubble of el.querySelectorAll("[data-prompt-key]")) {
		if (bubble.getBoundingClientRect().top <= threshold) active = bubble.dataset.promptKey
	}
	activePromptKey.value = active
}

function scrollToPrompt(key) {
	const target = scroller.value?.querySelector(`[data-prompt-key="${CSS.escape(key)}"]`)
	if (!target) return
	stick.value = false // don't let the autoscroller cancel the jump mid-stream
	target.scrollIntoView({ behavior: "smooth", block: "start" })
}

watch(
	() => prompts.value.length,
	() => void nextTick(updateActivePrompt),
)

function toBottom() {
	const el = scroller.value
	if (!el) return
	el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
	stick.value = true
}

function toggleTurn(turnKey) {
	const next = new Set(expandedTurnKeys.value)
	const opening = !next.has(turnKey)
	if (opening) next.add(turnKey)
	else next.delete(turnKey)
	expandedTurnKeys.value = next
	if (!opening) return
	// reveal the steps the fold just inserted below itself (no-op when visible)
	void nextTick(() => {
		const fold = scroller.value?.querySelector(`[data-turn-fold="${CSS.escape(turnKey)}"]`)
		fold?.nextElementSibling?.scrollIntoView({ block: "nearest", behavior: "smooth" })
	})
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
