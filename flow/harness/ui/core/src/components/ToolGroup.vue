<template>
	<div>
		<template v-for="step in steps" :key="step.call ? step.call.id : step.id">
			<ThoughtStep v-if="step.thought" :id="step.id" :block="step.thought" :live="!sealed && !!step.live" />
			<ToolStep v-else :step="step" :live="!sealed && isLive(step)" />
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
// a sub-agent's row runs on its child's clock: several can be live at once
const isLive = (step) => step === runningStep.value || (!!step.subagent?.running && !step.result)

const tailLabel = computed(() => {
	if (props.sealed || runningStep.value) return null
	const last = props.steps[props.steps.length - 1]
	if (!last) return null
	// a live trailing thought shimmers on its own row; every other wait (results
	// landed, tool arguments still streaming, a retry) shows the status here
	if (last.thought && last.live) return null
	return props.liveLabel ?? "Working"
})
</script>
