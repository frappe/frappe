<template>
	<div>
		<!-- streaming: the header is a single line that changes in place; sealed
		     (a text blob followed, or the run settled) it summarizes the activity.
		     Either way it's manually expandable to the individual steps. -->
		<button
			class="flex w-full items-center gap-1.5 text-left text-sm hover:text-ink-gray-8"
			:class="open ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5'"
			@click="open = !open"
		>
			<!-- min-w-0 + truncate keep arbitrarily long labels (full bash commands,
			     deep paths) on one clipped line instead of a centered wrap -->
			<span class="min-w-0 truncate" :class="!sealed || active ? 'flow-shimmer font-medium' : ''">
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
			class="mt-2 max-h-[420px] overflow-y-auto rounded-[10px] border border-outline-gray-1 bg-surface-gray-1"
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

import { stepLiveLabel, toolGroupLiveLabel, toolGroupSummary } from "../transcript.js"
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
// follow new steps and streamed thinking when scrolled to the bottom
watch(
	() => {
		const last = props.steps[props.steps.length - 1]
		return `${props.steps.length}:${last?.thought?.thinking?.length ?? 0}`
	},
	() => {
		const el = panelEl.value
		if (!open.value || !el) return
		const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
		if (atBottom) nextTick(() => (el.scrollTop = el.scrollHeight))
	}
)

const toolSteps = computed(() => props.steps.filter((s) => s.call))
const active = computed(() => toolSteps.value.some((s) => !s.result && !s.aborted))

const label = computed(() => {
	if (active.value) {
		const running = toolSteps.value.find((s) => !s.result && !s.aborted)
		return stepLiveLabel(running.call)
	}
	return toolGroupSummary(toolSteps.value.map((step) => step.call))
})

// While streaming: the executing step, else the freshest live signal.
const liveLine = computed(() => {
	return toolGroupLiveLabel(props.steps, props.liveLabel)
})
</script>
