<template>
	<PalettePanel title="Thinking" :back="!dropdown" :dropdown="dropdown" :query="query" @close="emit('close')" @back="emit('back')">
		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<button
				v-for="level in levels"
				:key="level.id"
				data-palette-item
				:aria-current="level.id === currentEffort ? 'true' : undefined"
				class="flow-palette-row"
				@click="choose(level.id)"
			>
				<span class="flex-none">{{ level.label }}</span>
				<span class="flow-palette-hint min-w-0 flex-1 truncate">{{ level.desc }}</span>
				<!-- the hint follows the label, so the tick takes the right edge -->
				<FeatherIcon v-if="level.id === currentEffort" name="check" class="h-4 w-4 flex-none" />
			</button>
			<div v-if="!levels.length" class="flow-palette-empty">
				No matching levels
			</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { EFFORTS, EFFORT_LABELS } from "../transcript.js"
import PalettePanel from "./PalettePanel.vue"

const props = defineProps({
	query: { type: String, default: "" }, // the composer's text after its "/"
	dropdown: { type: Boolean, default: false }, // hung from the model button, not over the composer
})
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
const levels = computed(() => {
	const q = props.query.trim().toLowerCase()
	return LEVELS.filter((level) => level.label.toLowerCase().includes(q))
})

// an open chat runs at its own level (none is the provider's default); a new chat at the last one picked
const currentEffort = computed(
	() => (flow.state.sessionId ? flow.state.conversation.reasoningEffort : flow.state.prefs.lastEffort) ?? "default",
)

function choose(id) {
	flow.selectEffort(id)
	emit("close")
}
</script>
