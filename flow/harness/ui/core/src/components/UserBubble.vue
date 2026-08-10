<template>
	<!-- pb-7 reserves the button row inside this component's own box, so the
	     absolute buttons can never overlap the next message -->
	<div class="group relative flex justify-end pb-7">
		<div class="flow-prose max-w-[76%] rounded-xl bg-surface-gray-2 px-3.5 py-2.5 text-ink-gray-9">
			<div v-if="text" class="whitespace-pre-wrap">{{ text }}</div>
			<div v-if="attachments.length" class="flex flex-wrap gap-1.5" :class="text ? 'mt-2' : ''">
				<span
					v-for="item in attachments"
					:key="item.id"
					class="flex max-w-full items-center gap-2 rounded-lg border border-outline-gray-2 bg-surface-white py-1 pl-1 pr-2.5"
				>
					<span
						class="grid h-6 w-6 flex-none place-items-center rounded-md bg-surface-gray-1 text-ink-gray-6"
					>
						<FeatherIcon :name="item.kind === 'image' ? 'image' : 'file-text'" class="h-3.5 w-3.5" />
					</span>
					<span class="truncate text-xs font-medium text-ink-gray-8">{{ item.name }}</span>
				</span>
			</div>
		</div>
		<span class="absolute bottom-0 right-0.5 flex items-center gap-1">
			<span
				v-if="time"
				class="mr-1 text-2xs text-ink-gray-4 opacity-0 transition-opacity group-hover:opacity-100"
			>{{ time }}</span>
			<button
				title="Rewind to this message"
				class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
				@click="confirmRewind"
			>
				<FeatherIcon name="rotate-ccw" class="h-3.5 w-3.5" />
			</button>
			<CopyButton
				:text="text"
				class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
			/>
		</span>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import { formatTime, userAttachments, userText } from "../transcript.js"
import CopyButton from "./CopyButton.vue"

const props = defineProps({ entry: { type: Object, required: true } })
const flow = inject("flow")
const time = computed(() => formatTime(props.entry.ts))
const text = computed(() => userText(props.entry))
const attachments = computed(() => userAttachments(props.entry))

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
