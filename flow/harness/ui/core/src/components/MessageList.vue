<template>
	<div class="relative min-h-0 flex-1">
	<div
		ref="scroller"
		class="h-full overflow-y-auto px-5"
		:class="prompts.length > 3 ? 'md:px-10' : ''"
		:style="{ scrollPaddingBottom: composerHeight + 24 + 'px' }"
		@scroll="onScroll"
		@mousedown="onMouseDown"
	>
		<!-- pad by the floating composer's height so "center" means the visible
		     area above it, not the full page -->
		<div
			v-if="empty"
			ref="emptyState"
			class="flex h-full flex-col items-center justify-center gap-5 text-center"
			:style="{ paddingBottom: composerHeight + 'px' }"
		>
			<slot name="empty">
				<!-- a step smaller on a phone, and smaller still where the heading would run out of room -->
				<BrandMark :size="52" class="min-h-0 shrink max-sm:!h-10 max-sm:!w-10" />
				<h2 class="text-balance text-4xl font-normal leading-snug tracking-[-0.01em] text-ink-gray-9 sm:text-6xl">What would you like to build?</h2>
			</slot>
		</div>
		<LoadingState
			v-else-if="loading"
			class="h-full justify-center text-sm text-ink-gray-5"
			:style="{ paddingBottom: composerHeight + 'px' }"
		/>
		<div
			v-else
			ref="thread"
			class="flow-thread mx-auto flex max-w-[800px] flex-col gap-5 pt-10"
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
					@toggle="toggleTurn(item)"
				/>
				<AssistantText
					v-else-if="item.kind === 'text'"
					:class="tightGap(i)"
					:block="item.block"
				/>
				<ThinkingBlock
					v-else-if="item.kind === 'thinking'"
					:id="item.key"
					:class="tightGap(i)"
					:block="item.block"
					:live="item.live"
				/>
				<ToolGroup
					v-else-if="item.kind === 'group'"
					:class="tightGap(i)"
					:steps="item.steps"
					:sealed="i < turnEnd - 1 || !conversation.running"
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
						class="grid h-6 w-6 place-items-center rounded-5 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					/>
					<!-- a host's own per-turn actions (Flow's feedback thumbs) -->
					<component
						:is="flow.options.turnActions"
						v-if="flow.options?.turnActions"
						:turn-key="item.turnKey"
						:text="item.text"
						:ts="item.ts"
					/>
					<span v-if="formatTime(item.ts)" class="text-2xs text-ink-gray-4">{{ formatTime(item.ts) }}</span>
				</div>
				<TurnFiles v-else-if="item.kind === 'turn-files'" class="flow-turn-files -mt-1" :files="item.files" />
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
					class="break-words rounded-6 border border-outline-red-1 bg-surface-red-1 px-3.5 py-2.5 text-sm text-ink-red-6"
				>
					{{ item.error.message }}
				</div>
			</template>

			<!-- the latest reply's suggested next messages, until the user says something -->
			<SuggestedReplies
				v-if="replies"
				:key="replies.key"
				:replies="replies.replies"
				:multi-select="replies.multiSelect"
				class="-mt-2"
				@send="(text) => flow.send(text)"
			/>

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
				<span class="flow-shimmer">{{ liveLabel }}</span>
			</div>

		</div>
	</div>

	<PromptRail
		v-if="prompts.length > 3"
		:prompts="prompts"
		:active-key="activePromptKey"
		@select="scrollToPrompt"
	/>

	<button
		v-if="!stick && !empty"
		class="absolute left-1/2 z-10 grid h-8 w-8 -translate-x-1/2 place-items-center rounded-full border border-outline-gray-2 bg-surface-base text-ink-gray-6 shadow-md hover:text-ink-gray-9"
		:style="{ bottom: composerHeight + 12 + 'px' }"
		title="Scroll to bottom"
		@click="toBottom"
	>
		<FeatherIcon name="arrow-down" class="h-4 w-4" />
	</button>
	<!-- a read-only chat has no composer to quote into -->
	<AddToChat v-if="!flow.state.session?.read_only" :within="scroller" />
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { buildItems, formatTime, panelIds, suggestedReplies, userAttachments, userText } from "../transcript.js"
import AddToChat from "./AddToChat.vue"
import AssistantText from "./AssistantText.vue"
import BrandMark from "./BrandMark.vue"
import CopyButton from "./CopyButton.vue"
import LoadingState from "./LoadingState.vue"
import PromptRail from "./PromptRail.vue"
import SuggestedReplies from "./SuggestedReplies.vue"
import ThinkingBlock from "./ThinkingBlock.vue"
import ToolGroup from "./ToolGroup.vue"
import TurnFiles from "./TurnFiles.vue"
import TurnFold from "./TurnFold.vue"
import UserBubble from "./UserBubble.vue"

const props = defineProps({
	// the thread to draw: a sub-agent's, else the session's
	conversation: { type: Object, default: null },
	// false where the user can't send, such as a read-only chat
	suggestions: { type: Boolean, default: true },
})
const flow = inject("flow")
const conversation = computed(() => props.conversation ?? flow.state.conversation)
// the session's own: a sub-agent's thread offers none
const replies = computed(() => (props.suggestions && !props.conversation ? suggestedReplies(conversation.value) : null))
const expandedTurnKeys = ref(new Set())
// rows (tool calls, thoughts) the user has open, by id
const openPanels = reactive(new Set())
provide("openPanels", openPanels)
const items = computed(() => buildItems(conversation.value, expandedTurnKeys.value, openPanels))

// nothing to draw yet: the empty state, or a loading line while a session opens
const blank = computed(() => !items.value.length && !conversation.value.running && !conversation.value.liveLabel)
const empty = computed(() => blank.value && !flow.state.loading)
const loading = computed(() => blank.value && flow.state.loading)
const composerHeight = inject("composerHeight", ref(120))
const lastTurnCopyIndex = computed(() =>
	items.value.findLastIndex((item) => item.kind === "turn-copy"),
)
const lastItem = computed(() => items.value[items.value.length - 1])
// the running turn ends above the steered bubbles waiting below it
const turnEnd = computed(() => items.value.length - (conversation.value.steering?.length ?? 0))

// Tool and thought rows carry their own py-2.5, so the thread gap over-spaces
// them: standalone thoughts stack like they do inside a group, and a row
// meeting a text blob or the turn fold gives back most of that padding.
function tightGap(i) {
	const isRow = (kind) => kind === "group" || kind === "thinking"
	const prev = items.value[i - 1]?.kind
	const cur = items.value[i]?.kind
	if (prev === "thinking" && cur === "thinking") return "-mt-5"
	const meetsText = (isRow(prev) && cur === "text") || (prev === "text" && isRow(cur))
	return meetsText || (prev === "turn-fold" && isRow(cur)) ? "-mt-1.5" : ""
}

// Streamed thinking and tool groups render their own status. The fallback is
// reserved for statuses that have no preview item yet.
const lastIsOpenGroup = computed(
	() => conversation.value.running && lastItem.value?.kind === "group",
)
const lastIsLiveThinking = computed(
	() => lastItem.value?.kind === "thinking" && lastItem.value.live,
)
// a message in flight has no server status yet, but the work has started; below a
// steered one, the turn above keeps its own status
const liveLabel = computed(() =>
	conversation.value.running && conversation.value.steering?.length
		? "Working"
		: conversation.value.liveLabel || (conversation.value.sending?.length ? "Working" : ""),
)
const showStandaloneStatus = computed(
	() => !!liveLabel.value && !lastIsOpenGroup.value && !lastIsLiveThinking.value,
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
// the view sat on the bottom at the last scroll or resize
let atBottom = true

function onScroll() {
	const el = scroller.value
	if (!el) return
	const distance = el.scrollHeight - el.scrollTop - el.clientHeight
	const goingUp = el.scrollTop < lastScrollTop
	lastScrollTop = el.scrollTop
	atBottom = distance < 4
	// any upward scroll unsticks; scrolling down re-sticks only once the view
	// actually reaches the bottom — re-pinning from ~80px away yanks the page
	// out of the user's hands mid-scroll
	if (distance < 4) stick.value = true
	else if (goingUp) stick.value = false
	updateActivePrompt()
}

// a clicked button, link or summary takes no focus, so a closing dialog can't scroll the list back to it
function onMouseDown(event) {
	if (event.target.closest("button, a[href], summary")) event.preventDefault()
}

// collapsing a fold, a tool group or a thought can leave the view at the bottom
// without any scroll event, so the thread's height is watched as well; a panel,
// the sidebar or the window resizing the list re-wraps the thread, so a view that
// sat on the bottom is put back there
const thread = ref(null)
let resizeObserver = null
// the empty state glides to its new place, not jumps, when its box changes size (a growing
// composer): centred, it moves by half what the box lost. Its children glide, as they stay inside
// the list where the box would spill out of it. They jump with the composer where they would start
// under it (a phone's keyboard took more than the room below them), with reduced motion, and as
// its width changes (a resized frame)
const emptyState = ref(null)
const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")
let emptyObserver = null
watch(emptyState, (el) => {
	emptyObserver?.disconnect()
	if (!el || typeof ResizeObserver === "undefined") return
	let height = null
	let width = null
	emptyObserver = new ResizeObserver(([entry]) => {
		const now = entry.contentRect.height
		const shift = height === null || entry.contentRect.width !== width ? 0 : (height - now) / 2
		height = now
		width = entry.contentRect.width
		const last = el.lastElementChild
		const room = last ? now - (last.offsetTop - el.offsetTop + last.offsetHeight) : 0
		if (!shift || shift > room || reducedMotion?.matches) return
		for (const child of el.children)
			child.animate?.([{ transform: `translateY(${shift}px)` }, { transform: "none" }], {
				duration: 250,
				easing: "ease-out",
			})
	})
	emptyObserver.observe(el)
})
onBeforeUnmount(() => emptyObserver?.disconnect())
onMounted(() => {
	if (typeof ResizeObserver === "undefined") return
	resizeObserver = new ResizeObserver((entries) => {
		const el = scroller.value
		if (!el) return
		if (stick.value && atBottom && entries.some((entry) => entry.target === el)) el.scrollTop = el.scrollHeight
		atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 4
		if (atBottom) stick.value = true
	})
	watch(
		thread,
		(el) => {
			resizeObserver.disconnect()
			resizeObserver.observe(scroller.value)
			if (el) resizeObserver.observe(el)
		},
		{ immediate: true },
	)
})
onBeforeUnmount(() => resizeObserver?.disconnect())

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

function toggleTurn(item) {
	const { turnKey, expanded } = item
	const next = new Set(expandedTurnKeys.value)
	if (expanded) {
		next.delete(turnKey)
		// an open row holds its turn unfolded, so folding closes the turn's rows
		for (const id of items.value.filter((i) => i.turnKey === turnKey).flatMap(panelIds)) openPanels.delete(id)
	} else next.add(turnKey)
	expandedTurnKeys.value = next
	if (expanded) return
	// reveal the steps the fold just inserted below itself (no-op when visible)
	void nextTick(() => {
		const fold = scroller.value?.querySelector(`[data-turn-fold="${CSS.escape(turnKey)}"]`)
		fold?.nextElementSibling?.scrollIntoView({ block: "nearest", behavior: "smooth" })
	})
}

// your own message belongs at the live end of the thread, wherever the view was
// when you sent or steered it
const sendingCount = computed(
	() => (conversation.value.sending?.length ?? 0) + (conversation.value.steering?.length ?? 0),
)
watch(sendingCount, (count, before) => {
	if (count > before) stick.value = true
})

watch(
	() => [
		conversation.value.entries.length,
		sendingCount.value,
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
		openPanels.clear()
	},
)
</script>
