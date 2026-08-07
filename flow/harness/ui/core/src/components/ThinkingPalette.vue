<template>
	<PalettePanel title="Thinking" back @close="emit('close')" @back="emit('back')">
		<div class="min-h-0 flex-1 overflow-y-auto p-1.5">
			<button
				v-for="level in LEVELS"
				:key="level.id"
				class="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left hover:bg-surface-gray-2"
				:class="{ 'bg-surface-gray-2': level.id === currentEffort }"
				@click="choose(level.id)"
			>
				<span class="min-w-0 flex-1">
					<span class="block text-xs font-medium leading-4 text-ink-gray-9">{{ level.label }}</span>
					<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">{{ level.desc }}</span>
				</span>
				<FeatherIcon
					v-if="level.id === currentEffort"
					name="check"
					class="h-4 w-4 flex-none text-ink-gray-7"
				/>
			</button>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { EFFORTS, EFFORT_LABELS } from "../transcript.js"
import PalettePanel from "./PalettePanel.vue"

const emit = defineEmits(["close", "back"])
const flow = inject("flow")

const DESCRIPTIONS = {
	default: "Let the provider decide",
	off: "No extended thinking",
	minimal: "A moment's thought",
	low: "Quick reasoning",
	medium: "Balanced depth",
	high: "Thorough reasoning",
	xhigh: "Extra thorough",
	max: "Everything the model has",
}

// order and ids come from the wire-level list, so a new effort needs only a description
const LEVELS = EFFORTS.map((id) => ({ id, label: EFFORT_LABELS[id], desc: DESCRIPTIONS[id] }))

const currentEffort = computed(
	() => flow.state.conversation.reasoningEffort ?? flow.state.prefs.lastEffort ?? "default",
)

function choose(id) {
	flow.selectEffort(id)
	emit("close")
}
</script>
