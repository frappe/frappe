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
				<AssistantText v-else-if="item.kind === 'text'" :block="item.block" />
				<ThinkingBlock v-else-if="item.kind === 'thinking'" :block="item.block" />
				<ToolGroup
					v-else-if="item.kind === 'group'"
					:steps="item.steps"
					:sealed="i < items.length - 1 || hasPartialText || !conversation.running"
					:live-label="conversation.liveLabel"
				/>
				<!-- the latest turn's copy button stays visible; older ones hover-reveal -->
				<div
					v-else-if="item.kind === 'turn-copy'"
					class="-mt-3 flex"
					:class="i === lastTurnCopyIndex ? '' : 'flow-turn-copy'"
				>
					<CopyButton
						:text="item.text"
						title="Copy response"
						class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					/>
				</div>
				<ApprovalCard v-else-if="item.kind === 'approval'" :calls="item.calls" :seq="item.seq" />
				<div
					v-else-if="item.kind === 'compaction'"
					class="flex items-center gap-3 py-1 text-2xs text-ink-gray-4"
				>
					<span class="h-px flex-1 bg-surface-gray-3" />
					<span>Context compacted ({{ item.entry.reason }})</span>
					<span class="h-px flex-1 bg-surface-gray-3" />
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

			<!-- live region: at most one status element. During a tool phase the
			     unsealed group above renders the in-place line, so nothing here. -->
			<ThinkingBlock
				v-if="conversation.partialThinking && !lastIsOpenGroup"
				:block="{ thinking: conversation.partialThinking }"
				live
			/>
			<!-- streaming text; a whitespace-only partial renders nothing.
			     computed: re-parse per token only, not on unrelated re-renders -->
			<div
				v-if="streamingHtml"
				class="flow-md flow-prose text-ink-gray-8"
				v-html="streamingHtml"
			/>
			<div
				v-if="conversation.liveLabel && !conversation.partialThinking && !lastIsOpenGroup"
				class="text-sm font-medium"
			>
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

import { renderMarkdown } from "../markdown.js"
import { buildItems } from "../transcript.js"
import ApprovalCard from "./ApprovalCard.vue"
import AssistantText from "./AssistantText.vue"
import BrandMark from "./BrandMark.vue"
import CopyButton from "./CopyButton.vue"
import ThinkingBlock from "./ThinkingBlock.vue"
import ToolGroup from "./ToolGroup.vue"
import UserBubble from "./UserBubble.vue"

const flow = inject("flow")
const conversation = computed(() => flow.state.conversation)
const items = computed(() => buildItems(conversation.value))

const empty = computed(() => !flow.state.sessionId && !flow.state.loading)
const composerHeight = inject("composerHeight", ref(120))
// boolean computed: flips only on empty↔non-empty, not per streamed token, so
// the v-for bindings don't re-evaluate on every delta. Only streamed *text*
// seals a group — inter-step thinking must not collapse it to "Ran N steps".
const hasPartialText = computed(() => !!conversation.value.partialText)
const lastTurnCopyIndex = computed(() =>
	items.value.findLastIndex((item) => item.kind === "turn-copy"),
)
const streamingHtml = computed(() => {
	const text = conversation.value.partialText
	return text.trim() ? renderMarkdown(text) : ""
})
// a running tool phase: the trailing group renders the single live line
const lastIsOpenGroup = computed(
	() =>
		conversation.value.running &&
		!hasPartialText.value &&
		items.value[items.value.length - 1]?.kind === "group",
)

const scroller = ref(null)
const stick = ref(true)

function onScroll() {
	const el = scroller.value
	if (!el) return
	stick.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function toBottom() {
	const el = scroller.value
	if (!el) return
	el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
	stick.value = true
}

watch(
	() => [
		conversation.value.entries.length,
		conversation.value.partialText,
		conversation.value.partialThinking,
		conversation.value.liveLabel,
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
	() => (stick.value = true),
)
</script>
