<template>
	<div>
		<!-- a run of calls on one line: the latest calls while the run works, then what they did -->
		<button
			v-if="folded"
			class="group flex w-full cursor-pointer items-baseline gap-2.5 pt-2 text-left md:pt-2.5"
			:class="open ? 'pb-1.5' : 'pb-2 md:pb-2.5'"
			:aria-expanded="open"
			@click="toggle"
		>
			<!-- the line is something to open, not a tool: a chevron in the icon's place -->
			<span
				class="lucide-chevron-right size-3.5 flex-none self-center text-ink-gray-5 transition-transform"
				:class="open ? 'rotate-90' : ''"
				aria-hidden="true"
			/>
			<span class="flex min-w-0 items-baseline text-base text-ink-gray-6 group-hover:text-ink-gray-8">
				<span class="min-w-0 truncate" :class="sealed ? '' : 'flow-shimmer'">{{ headline }}</span>
				<!-- a finished run says so when calls in it failed, without being opened -->
				<span v-if="sealed && failures" class="flex-none">
					<span class="whitespace-pre text-ink-gray-4"> · </span>
					<span class="text-ink-red-5">{{ failures }} failed</span>
				</span>
			</span>
		</button>
		<!-- rows sit tight; the block's own padding keeps a run's gap to the text around it
		     (opened, the line above supplies the top) -->
		<div v-if="!folded || open" ref="rows" :class="folded ? 'pb-0.5 md:pb-1' : 'py-0.5 md:py-1'">
			<template v-for="step in steps" :key="step.call ? step.call.id : step.id">
				<ThoughtStep v-if="step.thought" :id="step.id" :block="step.thought" :live="!sealed && !!step.live" />
				<ToolStep v-else :step="step" :live="!sealed && isLive(step)" />
			</template>
		</div>
		<!-- results landed but the run continues (model deciding the next step):
		     no row carries the live signal, so a trailing status line does -->
		<div v-if="tailLabel && !folded" class="py-2 text-base-medium md:py-2.5">
			<span class="flow-shimmer">{{ tailLabel }}</span>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"

import { usePanelOpen } from "../panels.js"
import { compactDisplayText, displayText, stepDecision, stepDoneLabel, stepLiveLabel } from "../transcript.js"
import ThoughtStep from "./ThoughtStep.vue"
import ToolStep from "./ToolStep.vue"

const props = defineProps({
	// the group's key: names its open state in the message list
	id: { type: String, default: null },
	steps: { type: Array, required: true },
	// sealed = a text blob follows this group, or the run settled
	sealed: { type: Boolean, default: true },
	// freshest live status (conversation.liveLabel) — used only while unsealed
	liveLabel: { type: String, default: null },
})

const flow = inject("flow", null)
const panels = inject("openPanels", null)

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

// One line for the run unless the user asked for every row (prefs.separateToolCalls): always
// while it works, then only where it holds more than one call.
const calls = computed(() => props.steps.filter((step) => step.call).length)
const folded = computed(() => !flow?.state?.prefs?.separateToolCalls && (!props.sealed || calls.value > 1))
// the latest call holds the line until the next one, so fast calls stay readable; only a real wait replaces it
const WAITS = new Set(["Retrying", "Compacting context"])
const headline = computed(() => {
	if (props.sealed) return doneLine()
	if (!runningStep.value && WAITS.has(props.liveLabel)) return props.liveLabel
	return latestCalls() ?? tailLabel.value ?? "Thinking"
})

// calls that errored or the user refused
const failures = computed(
	() =>
		props.steps.filter(
			(step) => step.result?.is_error === true || ["denied", "cancelled"].includes(stepDecision(step.result)?.status),
		).length,
)

// the latest call, joined with the back-to-back calls of its kind before it: "Reading file a.js, b.js"
function latestCalls() {
	const steps = props.steps.slice(0, props.steps.findLastIndex((step) => step.call) + 1).reverse()
	if (!steps.length) return null
	const [lead, subject] = callParts(steps[0])
	const subjects = [subject]
	for (const step of steps.slice(1)) {
		if (!subject || step.call?.name !== steps[0].call.name) break
		const [otherLead, other] = callParts(step)
		if (otherLead !== lead || !other) break
		if (!subjects.includes(other)) subjects.unshift(other)
	}
	return lead + subjects.join(", ")
}

// what the run did, each kind of call once, in order: "Read records, Ran reports"
function doneLine() {
	const done = props.steps.filter((step) => step.call).map((step) => present(step).done ?? stepDoneLabel(step.call.name))
	return [...new Set(done)].join(", ")
}

// a call as its verb and its subject: a host's own words for its tools, else the call's live label
function callParts(step) {
	const call = step.call
	const meta = present(step)
	if (call.display?.length || !meta.label) {
		const line = compactDisplayText(stepLiveLabel(call), flow?.state?.session?.config?.cwd)
		const at = call.display?.findIndex((segment) => segment.arg) ?? -1
		const lead = at > 0 ? displayText(call.display.slice(0, at)) : line
		return line.startsWith(lead) ? [lead, line.slice(lead.length)] : [line, ""]
	}
	return meta.subject ? [`${meta.label} · `, meta.subject] : [meta.label, ""]
}

function present(step) {
	const call = step.call
	return flow?.options?.presentTool?.(call.name, call.arguments ?? call.args ?? {}, step.result) ?? {}
}

const rows = ref(null)
// a row the user has open is never hidden, so folding the run closes its rows
const ownOpen = usePanelOpen(() => props.id)
const rowIds = computed(() => props.steps.map((step) => step.call?.id ?? step.id))
const open = computed(() => ownOpen.value || rowIds.value.some((id) => panels?.has(id)))
function toggle() {
	if (open.value) {
		ownOpen.value = false
		for (const id of rowIds.value) panels?.delete(id)
		return
	}
	ownOpen.value = true
	// opened near the bottom edge, the rows would start off-screen
	void nextTick(() => rows.value?.firstElementChild?.scrollIntoView({ block: "nearest", behavior: "smooth" }))
}
</script>
