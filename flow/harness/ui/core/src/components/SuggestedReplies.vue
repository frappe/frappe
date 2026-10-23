<template>
	<!-- a tap sends a reply; a question taking several answers ticks them, then sends them together -->
	<div class="flex flex-col items-start gap-2.5">
		<div class="flex flex-wrap items-center gap-1.5" role="group" :aria-label="multiSelect ? 'Pick answers' : 'Suggested replies'">
			<button
				v-for="reply in replies"
				:key="reply"
				type="button"
				class="flex h-8 min-w-0 max-w-full items-center gap-1.5 rounded-full border px-3 text-sm"
				:class="
					picked.includes(reply)
						? 'border-outline-gray-4 bg-surface-gray-2 text-ink-gray-9'
						: 'border-outline-gray-2 bg-surface-base text-ink-gray-7 hover:bg-surface-gray-2 hover:text-ink-gray-9'
				"
				:title="reply"
				:aria-pressed="multiSelect ? picked.includes(reply) : undefined"
				@click="tap(reply)"
			>
				<FeatherIcon
					v-if="multiSelect"
					:name="picked.includes(reply) ? 'check-square' : 'square'"
					class="h-3.5 w-3.5 flex-none"
				/>
				<span class="truncate">{{ reply }}</span>
			</button>
		</div>
		<!-- keeps its room while hidden: appearing would push it under the composer -->
		<button
			v-if="multiSelect"
			type="button"
			class="-mb-[30px] flex h-8 flex-none items-center gap-1.5 rounded-full bg-surface-gray-10 px-3 text-sm font-medium text-ink-base hover:opacity-90"
			:class="{ invisible: !picked.length }"
			@click="$emit('send', replies.filter((reply) => picked.includes(reply)).join(', '))"
		>
			Send
			<FeatherIcon name="arrow-up" class="h-3.5 w-3.5" />
		</button>
	</div>
</template>

<script setup>
import { ref } from "vue"

import { layout } from "../layout.js"
import FeatherIcon from "./FeatherIcon.vue"

const props = defineProps({
	replies: { type: Array, required: true },
	multiSelect: { type: Boolean, default: false },
})
const emit = defineEmits(["send"])

const picked = ref([])

// On a phone they come up as the run ends, under a finger that may be going elsewhere:
// a tap in their first moment does nothing
const shownAt = Date.now()
function tap(reply) {
	if (layout.phone && Date.now() - shownAt < 400) return
	if (!props.multiSelect) return emit("send", reply)
	picked.value = picked.value.includes(reply) ? picked.value.filter((item) => item !== reply) : [...picked.value, reply]
}
</script>
