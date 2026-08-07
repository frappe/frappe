<template>
	<div>
		<!-- streaming: the header is a single line that changes in place; sealed
		     (a text blob followed, or the run settled) it becomes "Ran N steps".
		     Either way it's manually expandable to the individual steps. -->
		<button
			class="flex items-center gap-1.5 text-sm hover:text-ink-gray-8"
			:class="open ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5'"
			@click="open = !open"
		>
			<span :class="!sealed || active ? 'flow-shimmer font-medium' : ''">
				{{ sealed ? label : liveLine }}
			</span>
			<FeatherIcon
				name="chevron-right"
				class="mt-px h-3.5 w-3.5 flex-none transition-transform"
				:class="open ? 'rotate-90' : ''"
			/>
		</button>

		<div
			v-if="open"
			ref="panelEl"
			class="mt-2 overflow-hidden rounded-[10px] border border-outline-gray-1 bg-surface-gray-1"
		>
			<template v-for="(step, i) in steps" :key="step.call ? step.call.id : `thought-${i}`">
				<ThoughtStep
					v-if="step.thought"
					:block="step.thought"
					:class="i > 0 ? 'border-t border-outline-gray-1' : ''"
				/>
				<ToolStep v-else :step="step" :class="i > 0 ? 'border-t border-outline-gray-1' : ''" />
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { stepLabel } from "../transcript.js"
import ThoughtStep from "./ThoughtStep.vue"
import ToolStep from "./ToolStep.vue"

const props = defineProps({
	steps: { type: Array, required: true },
	// sealed = a text blob follows this group, or the run settled
	sealed: { type: Boolean, default: true },
	// freshest live status (conversation.liveLabel) — used only while unsealed
	liveLabel: { type: String, default: null },
})

// manual toggle only — never auto-opened, so streaming can't flap the panel
const open = ref(false)
const panelEl = ref(null)
// scroll expansions near the viewport bottom clear of the composer
watch(open, (value) => {
	if (value) nextTick(() => panelEl.value?.scrollIntoView({ block: "nearest", behavior: "smooth" }))
})

const toolSteps = computed(() => props.steps.filter((s) => s.call))
const active = computed(() => toolSteps.value.some((s) => !s.result && !s.aborted))

const label = computed(() => {
	if (active.value) {
		const running = toolSteps.value.find((s) => !s.result)
		return running ? stepLabel(running.call.name) : "Working…"
	}
	return toolSteps.value.length === 1
		? stepLabel(toolSteps.value[0].call.name)
		: `Ran ${toolSteps.value.length} steps`
})

// While streaming: the executing step, else the freshest signal we have. The
// line holds the last tool label through inter-step thinking — never "Thinking…".
const liveLine = computed(() => {
	const running = toolSteps.value.find((s) => !s.result)
	if (running) return stepLabel(running.call.name) + "…"
	const last = toolSteps.value[toolSteps.value.length - 1]
	return props.liveLabel ?? (last ? stepLabel(last.call.name) + "…" : "Working…")
})
</script>
