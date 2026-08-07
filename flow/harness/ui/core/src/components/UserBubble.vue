<template>
	<!-- pb-7 reserves the button row inside this component's own box, so the
	     absolute buttons can never overlap the next message -->
	<div class="group relative flex justify-end pb-7">
		<div
			class="flow-prose max-w-[76%] whitespace-pre-wrap rounded-xl bg-surface-gray-2 px-3.5 py-2.5 text-ink-gray-9"
		>{{ entry.content }}</div>
		<span class="absolute bottom-0 right-0.5 flex gap-1">
			<button
				title="Rewind to this message"
				class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
				@click="confirmRewind"
			>
				<FeatherIcon name="rotate-ccw" class="h-3.5 w-3.5" />
			</button>
			<CopyButton
				:text="entry.content"
				class="grid h-6 w-6 place-items-center rounded-md text-ink-gray-4 opacity-0 transition-opacity hover:bg-surface-gray-2 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover:opacity-100"
			/>
		</span>
	</div>
</template>

<script setup>
import { inject } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import CopyButton from "./CopyButton.vue"

const props = defineProps({ entry: { type: Object, required: true } })
const flow = inject("flow")

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
