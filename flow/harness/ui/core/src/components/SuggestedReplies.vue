<template>
	<!-- a tap sends a reply; a question taking several answers ticks them, then sends them together -->
	<div class="flex flex-col items-start gap-2.5">
		<div class="flex max-w-full flex-wrap items-center gap-1.5" role="group" :aria-label="multiSelect ? 'Pick answers' : 'Suggested replies'">
			<Button
				v-for="reply in replies"
				:key="reply"
				size="sm"
				variant="outline"
				class="min-w-0 max-w-full"
				:label="reply"
				:title="reply"
				:data-state="picked.includes(reply) ? 'active' : undefined"
				:aria-pressed="multiSelect ? picked.includes(reply) : undefined"
				@click="tap(reply)"
			>
				<template v-if="multiSelect" #prefix>
					<span
						class="size-4 flex-none"
						:class="picked.includes(reply) ? 'lucide-square-check' : 'lucide-square'"
						aria-hidden="true"
					/>
				</template>
			</Button>
		</div>
		<!-- keeps its room while hidden: appearing would push it under the composer -->
		<Button
			v-if="multiSelect"
			size="sm"
			variant="solid"
			label="Send"
			icon-right="lucide-arrow-up"
			class="-mb-[26px]"
			:class="{ invisible: !picked.length }"
			@click="$emit('send', replies.filter((reply) => picked.includes(reply)).join(', '))"
		/>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { Button } from "frappe-ui/src/components/Button"

import { layout } from "../layout.js"

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
