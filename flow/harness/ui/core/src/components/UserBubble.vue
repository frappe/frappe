<template>
	<!-- pb-7 reserves the button row inside this component's own box, so the
	     absolute buttons can never overlap the next message -->
	<div class="group relative flex justify-end pb-7">
		<div class="flow-prose max-w-[76%] rounded-7 bg-surface-gray-2 px-3.5 py-2.5 text-ink-gray-9">
			<div v-if="attachments.length" class="flex flex-wrap gap-1.5" :class="text ? 'mb-2' : ''">
				<template v-for="item in attachments" :key="item.id">
					<button
						v-if="previews[item.id]"
						class="h-[72px] w-[72px] flex-none cursor-zoom-in overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-sm"
						:title="item.name"
						:aria-label="`View ${item.name}`"
						@click="viewer = item"
					>
						<img :src="previews[item.id]" :alt="item.name" class="h-full w-full object-cover" />
					</button>
					<span
						v-else
						class="flex max-w-full items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-base py-1 pl-1 pr-2.5"
					>
						<span
							class="grid h-6 w-6 flex-none place-items-center rounded-5 bg-surface-gray-1 text-ink-gray-6"
						>
							<FeatherIcon :name="item.kind === 'image' ? 'image' : 'file-text'" class="h-3.5 w-3.5" />
						</span>
						<span class="truncate text-xs font-medium text-ink-gray-8">{{ item.name }}</span>
					</span>
				</template>
			</div>
			<div
				v-if="text"
				ref="textEl"
				class="whitespace-pre-wrap"
				:class="expanded ? '' : 'line-clamp-[12]'"
			>{{ text }}</div>
			<button
				v-if="clampable"
				class="mt-1.5 text-xs font-medium text-ink-gray-5 hover:text-ink-gray-8"
				@click="expanded = !expanded"
			>
				{{ expanded ? "Show less" : "Show more" }}
			</button>
		</div>
		<span class="absolute bottom-0 right-0.5 flex items-center gap-1">
			<span
				v-if="time"
				class="mr-1 text-2xs text-ink-gray-4 opacity-0 transition-opacity group-hover:opacity-100"
			>{{ time }}</span>
			<button
				title="Rewind to this message"
				class="grid h-6 w-6 place-items-center rounded-5 text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
				@click="confirmRewind"
			>
				<FeatherIcon name="rotate-ccw" class="h-3.5 w-3.5" />
			</button>
			<CopyButton
				:text="text"
				class="grid h-6 w-6 place-items-center rounded-5 text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
			/>
		</span>
		<ImageViewer v-if="viewer" :src="previews[viewer.id]" :alt="viewer.name" @close="viewer = null" />
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import { formatTime, userAttachments, userText } from "../transcript.js"
import CopyButton from "./CopyButton.vue"
import ImageViewer from "./ImageViewer.vue"

const props = defineProps({ entry: { type: Object, required: true } })
const flow = inject("flow")
const time = computed(() => formatTime(props.entry.ts))
const text = computed(() => userText(props.entry))
const attachments = computed(() => userAttachments(props.entry))

const previews = ref({}) // attachment id → object URL of the stored image
const viewer = ref(null)
let disposed = false

onMounted(() => {
	const sid = flow.state.sessionId
	if (!sid) return
	for (const item of attachments.value) {
		if (item.kind !== "image" || !item.id) continue
		flow.client
			.attachmentBlob(sid, item.id)
			.then((blob) => {
				const url = URL.createObjectURL(blob)
				if (disposed) URL.revokeObjectURL(url)
				else previews.value[item.id] = url
			})
			.catch(() => {
				// A missing historical attachment falls back to its filename badge.
			})
	}
})
onBeforeUnmount(() => {
	disposed = true
	for (const url of Object.values(previews.value)) URL.revokeObjectURL(url)
})

// show the toggle only when the 12-line clamp actually truncated
const expanded = ref(false)
const textEl = ref(null)
const clampable = ref(false)
onMounted(() => {
	const el = textEl.value
	clampable.value = !!el && el.scrollHeight > el.clientHeight + 1
})

function confirmRewind() {
	dialog.confirm({
		title: "Rewind to this message?",
		message:
			"Everything after this point is removed from the conversation, and the message returns to the composer so you can edit and resend it.",
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
