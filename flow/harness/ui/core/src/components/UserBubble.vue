<template>
	<!-- pb-7 reserves the button row inside this component's own box, so the
	     absolute buttons can never overlap the next message -->
	<div class="group relative flex justify-end pb-7">
		<div class="flow-prose max-w-[76%] rounded-7 bg-surface-gray-2 px-3.5 py-2.5 text-ink-gray-9">
			<div v-if="imageTiles.length" class="flex flex-wrap gap-1.5" :class="hasText || chips.length ? 'mb-2' : ''">
				<button
					v-for="item in imageTiles"
					:key="item.id"
					class="h-[72px] w-[72px] flex-none cursor-zoom-in overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-sm"
					:title="item.name"
					:aria-label="`View ${item.name}`"
					@click="viewer = item"
				>
					<img :src="previews[item.id]" :alt="item.name" class="h-full w-full object-cover" />
				</button>
			</div>
			<div v-if="chips.length" class="flex flex-wrap items-center gap-1.5" :class="hasText ? 'mb-2' : ''">
				<span
					v-for="chip in chips"
					:key="chip.key"
					class="flex h-8 max-w-full items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-base pl-1 pr-2.5"
					:title="chip.title"
				>
					<span class="grid h-6 w-6 flex-none place-items-center rounded-5 bg-surface-gray-1 text-ink-gray-6">
						<FeatherIcon :name="chip.icon" class="h-3.5 w-3.5" />
					</span>
					<span class="truncate text-xs font-medium text-ink-gray-8">{{ chip.label }}</span>
				</span>
			</div>
			<div
				v-if="hasText"
				ref="textEl"
				class="whitespace-pre-wrap break-words"
				:class="expanded ? '' : 'line-clamp-[12]'"
			><div
					v-if="quotes.length"
					class="flex flex-col gap-2"
					:class="body ? 'mb-2' : ''"
				><blockquote
						v-for="(quote, i) in quotes"
						:key="i"
						class="border-l-2 border-outline-gray-2 pl-3 text-ink-gray-6"
					>{{ quote }}</blockquote></div><span v-for="(part, i) in parts" :key="i" :class="{ 'text-ink-blue-6': part.skill }">{{ part.text }}</span></div>
			<button
				v-if="clampable"
				class="mt-1.5 text-xs font-medium text-ink-gray-5 hover:text-ink-gray-8"
				@click="expanded = !expanded"
			>
				{{ expanded ? "Show less" : "Show more" }}
			</button>
		</div>
		<span class="absolute bottom-0 right-0.5 flex items-center gap-1">
			<span v-if="time" class="flow-hover-reveal mr-1 text-2xs text-ink-gray-4">{{ time }}</span>
			<button
				v-if="rewindable"
				title="Rewind to this message"
				class="flow-hover-reveal grid h-6 w-6 place-items-center rounded-5 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				@click="confirmRewind"
			>
				<FeatherIcon name="rotate-ccw" class="h-3.5 w-3.5" />
			</button>
			<CopyButton
				:text="text"
				class="flow-hover-reveal grid h-6 w-6 place-items-center rounded-5 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
			/>
		</span>
		<ImageViewer v-if="viewer" :src="previews[viewer.id]" :alt="viewer.name" @close="viewer = null" />
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import {
	codeRefLabel,
	formatTime,
	invokedSkills,
	skillSegments,
	splitCodeRefs,
	splitQuotes,
	userAttachments,
	userText,
} from "../transcript.js"
import CopyButton from "./CopyButton.vue"
import ImageViewer from "./ImageViewer.vue"

const props = defineProps({ entry: { type: Object, required: true } })
const flow = inject("flow")
const time = computed(() => formatTime(props.entry.ts))
const text = computed(() => userText(props.entry)) // full text, for copy
const attachments = computed(() => userAttachments(props.entry))
const split = computed(() => splitCodeRefs(text.value))
const quoted = computed(() => splitQuotes(split.value.body))
const body = computed(() => quoted.value.body)
const quotes = computed(() => quoted.value.quotes)
const hasText = computed(() => !!body.value || quotes.value.length > 0)
// no rewind point: a message not in the log yet, a sub-agent's task, a steered message, a read-only chat
const rewindable = computed(
	() =>
		flow.capabilities?.rewind &&
		props.entry.seq != null &&
		!props.entry.subagent_id &&
		!flow.state.conversation.steeredSeqs?.includes(props.entry.seq) &&
		!flow.state.session?.read_only,
)
// skill commands stay blue, as in the composer; a bubble still sending knows only the catalog
const parts = computed(() => {
	const sending = props.entry.seq == null ? (flow.state.skills ?? []).map((skill) => skill.name) : []
	return skillSegments(body.value, invokedSkills(props.entry) ?? sending)
})
// images stage as full previews on their own row; code refs and files share one row of chips
const imageTiles = computed(() => attachments.value.filter((item) => previews.value[item.id]))
const chips = computed(() => [
	...split.value.refs.map((ref) => ({
		key: `ref:${ref.path}:${ref.start}-${ref.end}`,
		icon: "code",
		label: codeRefLabel(ref),
		title: `${ref.path}:${ref.start}-${ref.end}`,
	})),
	...attachments.value
		.filter((item) => !previews.value[item.id])
		.map((item) => ({ key: item.id, icon: item.kind === "image" ? "image" : "file-text", label: item.name, title: item.name })),
])

const previews = ref({}) // attachment id → object URL of the stored image
const viewer = ref(null)
let disposed = false

onMounted(() => {
	const sid = flow.state.sessionId
	if (!sid) return
	for (const item of attachments.value) {
		if (item.kind !== "image" || !item.id) continue
		flow.attachmentPreview(sid, item.id).then((url) => {
			if (!url) return
			if (disposed) URL.revokeObjectURL(url)
			else previews.value[item.id] = url
		})
	}
})
onBeforeUnmount(() => {
	disposed = true
	for (const url of Object.values(previews.value)) URL.revokeObjectURL(url)
})

// show the toggle only when the 12-line clamp actually truncated, measured again when the
// thread narrows (a panel opening, a phone turning)
const expanded = ref(false)
const textEl = ref(null)
const clampable = ref(false)
let resizer = null
function measure() {
	const el = textEl.value
	if (el && !expanded.value) clampable.value = el.scrollHeight > el.clientHeight + 1
}
onMounted(() => {
	measure()
	if (typeof ResizeObserver === "undefined" || !textEl.value) return
	resizer = new ResizeObserver(measure)
	resizer.observe(textEl.value)
})
onBeforeUnmount(() => resizer?.disconnect())

function confirmRewind() {
	dialog.confirm({
		title: "Rewind to this message?",
		size: "lg",
		message:
			"Everything from this point is removed from the conversation. Changes made by tools are not reverted.",
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Rewind",
				variant: "solid",
				theme: "red",
				onClick: () => flow.rewindToMessage(props.entry),
			},
		],
	})
}
</script>
