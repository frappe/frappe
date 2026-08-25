<template>
	<div>
		<template v-for="(step, i) in steps" :key="step.call ? step.call.id : `thought-${i}`">
			<ThoughtStep v-if="step.thought" :block="step.thought" />
			<ToolStep v-else :step="step" :live="!sealed && step === runningStep" />
		</template>
		<!-- results landed but the run continues (model deciding the next step):
		     no row carries the live signal, so a trailing status line does -->
		<div v-if="tailLabel" class="py-2.5 text-sm font-medium">
			<span class="flow-shimmer">{{ tailLabel }}</span>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue"

import { stepLabel, stepLiveLabel } from "../transcript.js"
import ThoughtStep from "./ThoughtStep.vue"
import ToolStep from "./ToolStep.vue"

const props = defineProps({
	steps: { type: Array, required: true },
	// sealed = a text blob follows this group, or the run settled
	sealed: { type: Boolean, default: true },
	// freshest live status (conversation.liveLabel) — used only while unsealed
	liveLabel: { type: String, default: null },
})

const runningStep = computed(
	() => props.steps.find((s) => s.call && !s.result && !s.aborted) ?? null,
)

const tailLabel = computed(() => {
	if (props.sealed || runningStep.value) return null
	const last = props.steps[props.steps.length - 1]
	// a trailing thought streams its own preview line
	if (!last || last.thought) return null
	// a liveLabel that only repeats the settled row above adds nothing
	const label = props.liveLabel
	if (!label || label === stepLabel(last.call.name) || label === stepLiveLabel(last.call))
		return "Thinking"
	return label
})
</script>
