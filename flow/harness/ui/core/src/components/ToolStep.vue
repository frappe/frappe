<template>
	<div>
		<component
			:is="expandable || link ? 'button' : 'div'"
			class="flex w-full items-baseline gap-2.5 py-2.5 text-left"
			:class="[expandable || link ? 'group cursor-pointer' : '', live ? 'flow-tool-live' : '']"
			@click="link ? flow.openSubagent(subagentId(step.call)) : expandable && (open = !open)"
		>
			<!-- leading slot doubles as the disclosure control: the tool icon yields
			     to a chevron on hover, and to the rotated (close) chevron while open -->
			<span class="relative h-3.5 w-3.5 flex-none self-center text-ink-gray-5">
				<FeatherIcon
					:name="icon"
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : expandable || link ? 'group-hover:opacity-0' : ''"
				/>
				<FeatherIcon
					v-if="expandable || link"
					name="chevron-right"
					class="absolute inset-0 h-3.5 w-3.5 transition-[opacity,transform]"
					:class="open ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'"
				/>
			</span>
			<!-- template text renders like a label, argument values like a subject -->
			<span v-if="displaySegments.length" class="min-w-0 flex-1 truncate text-sm">
				<span
					v-for="(segment, j) in displaySegments"
					:key="j"
					:class="
						!segment.arg
							? 'font-medium text-ink-gray-9'
							: step.call.name === 'bash'
								? 'font-mono text-xs text-ink-gray-5 group-hover:text-ink-gray-7'
								: 'text-ink-gray-5 group-hover:text-ink-gray-7'
					"
				>{{ segment.text }}</span>
			</span>
			<template v-else>
				<span class="flex-none text-sm font-medium text-ink-gray-9">{{ label }}</span>
				<span
					class="min-w-0 flex-1 truncate text-sm text-ink-gray-5 group-hover:text-ink-gray-7"
					:class="step.call.name === 'bash' ? 'font-mono text-xs' : ''"
				>{{ subject }}</span>
			</template>
			<!-- edits get a Codex-style colored diffstat; everything else the plain stat -->
			<span v-if="diffStat" class="flex-none font-mono text-xs">
				<span class="text-ink-green-6">+{{ diffStat.added }}</span>
				<span class="ml-1 text-ink-red-6">-{{ diffStat.removed }}</span>
			</span>
			<span v-else-if="stat" class="flex-none text-xs" :class="statClass">{{ stat }}</span>
		</component>

		<div
			v-if="open && expandable"
			ref="payloadEl"
			class="mb-1.5 mt-1 overflow-hidden rounded-[10px] border border-outline-gray-1 bg-surface-base"
		>
			<div v-if="meta.argsComponent && !resultView" class="border-b border-outline-gray-1">
				<component :is="meta.argsComponent" :arguments="args" />
			</div>
			<!-- a call the user denied, cancelled, or redirected -->
			<div v-if="decision" class="px-3 py-2.5">
				<div class="text-xs font-medium" :class="statClass">{{ decisionTitle }}</div>
				<div v-if="decision.user_feedback" class="mt-1 text-xs leading-relaxed text-ink-gray-6">
					“{{ decision.user_feedback }}”
				</div>
			</div>

			<component :is="resultView" v-else-if="resultView" :arguments="args" :result="step.result" />

			<template v-else-if="step.result">
				<div class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-1.5">
					<span class="min-w-0 flex-1 truncate text-2xs text-ink-gray-4">{{ panelNote }}</span>
					<span v-if="duration" class="flex-none font-mono text-2xs text-ink-gray-5">{{ duration }}</span>
					<span
						v-if="exitChip"
						class="flex-none rounded-4 px-1.5 py-px font-mono text-2xs font-medium"
						:class="failed ? 'bg-surface-red-1 text-ink-red-6' : 'bg-surface-green-1 text-ink-green-6'"
					>{{ exitChip }}</span>
					<CopyButton
						:text="diffLines ? details.diff : output"
						class="grid h-5 w-5 flex-none place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					/>
				</div>
				<pre
					v-if="diffLines"
					class="m-0 grid max-h-[260px] overflow-auto py-2 font-mono text-xs leading-[1.7]"
				><span
					v-for="(line, i) in diffLines"
					:key="i"
					class="block px-3.5"
					:class="lineClass(line)"
				>{{ line }}</span></pre>
				<pre
					v-else
					class="m-0 max-h-[200px] overflow-y-auto whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-[1.65] text-ink-gray-6"
				>{{ output }}</pre>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { usePanelOpen } from "../panels.js"
import {
	compactDisplayText,
	stepDecision,
	stepIcon,
	stepLabel,
	stepStat,
	stepSubject,
	subagentId,
} from "../transcript.js"
import CopyButton from "./CopyButton.vue"

const props = defineProps({
	step: { type: Object, required: true },
	// this step is the one executing right now — its row carries the sweep
	live: { type: Boolean, default: false },
})

const open = usePanelOpen(() => props.step.call.id)

const flow = inject("flow", null)
const cwd = computed(() => flow?.state?.session?.config?.cwd ?? null)

const displaySegments = computed(() =>
	(props.step.call.display ?? []).map((segment) =>
		segment.arg ? { ...segment, text: compactDisplayText(segment.text, cwd.value) } : segment,
	),
)

// a host describes its own tools; the daemon's have display segments or defaults
const args = computed(() => props.step.call.arguments ?? props.step.call.args ?? {})
const meta = computed(() => {
	const call = props.step.call
	return flow?.options?.presentTool?.(call.name, args.value, props.step.result) ?? {}
})
const icon = computed(() => meta.value.icon ?? stepIcon(props.step.call.name))
const label = computed(() => meta.value.label ?? stepLabel(props.step.call.name))
const subject = computed(() =>
	compactDisplayText(meta.value.subject ?? stepSubject(props.step.call), cwd.value),
)
const failed = computed(() => props.step.result?.is_error === true)
const details = computed(() => props.step.result?.details ?? {})
const output = computed(() => props.step.result?.content ?? "")

// a sub-agent's row opens the child's thread in the workspace panel instead of a
// dropdown, unless the host has no panel or the call was refused before any child ran
const link = computed(
	() =>
		props.step.call.name === "subagent" &&
		flow?.options?.workspace !== false &&
		(!props.step.result || "end_reason" in details.value),
)

const decision = computed(() => stepDecision(props.step.result))
const decisionTitle = computed(
	() =>
		({
			denied: "Denied by user",
			cancelled: "Cancelled by user",
			redirect: "User asked for changes",
		})[decision.value?.status] ?? "",
)

const stat = computed(() => {
	if (props.step.aborted && !props.step.result) return "aborted"
	// a running sub-agent's row carries what the child is doing right now
	const child = props.step.subagent
	if (child?.running && !props.step.result) return child.liveLabel ?? "Working"
	// a host describes its own tool, like icon and label — but what the user decided
	// about the call outranks anything the tool says about itself
	if (decision.value) return stepStat(props.step)
	return meta.value.stat || stepStat(props.step) || ""
})
const statClass = computed(() => {
	if (decision.value) return decision.value.status === "redirect" ? "text-ink-amber-6" : "text-ink-red-6"
	return failed.value ? "text-ink-red-6" : "text-ink-gray-4"
})

const resultView = computed(() =>
	meta.value.resultComponent && props.step.result && !failed.value && !decision.value
		? meta.value.resultComponent
		: null,
)

const diffLines = computed(() =>
	typeof details.value.diff === "string" && details.value.diff ? details.value.diff.split("\n") : null,
)

// lines added/removed, from the server's authoritative count (absent on old
// rows and on decision envelopes, which have no details)
const diffStat = computed(() => {
	const d = details.value
	if (d.lines_added === undefined && d.lines_removed === undefined) return null
	return { added: d.lines_added ?? 0, removed: d.lines_removed ?? 0 }
})

// dumping file contents inline is noise; expand only where the payload is the
// point (command output, search hits, diffs, custom tool results) or the user
// intervened — a host describing its own tool decides for that tool instead
// expanding near the bottom edge would reveal the payload off-screen;
// nudge it into view (no-op when it is already visible)
const payloadEl = ref(null)
watch(payloadEl, (el) => el?.scrollIntoView({ block: "nearest", behavior: "smooth" }))

const expandable = computed(() => {
	if (link.value) return false
	if (failed.value || decision.value) return true
	if (meta.value.expandable === false) return false
	if (meta.value.argsComponent) return true
	if (!props.step.result) return false
	if (diffLines.value || resultView.value) return true
	if (["read", "write", "edit"].includes(props.step.call.name)) return false
	return !!output.value
})

const duration = computed(() =>
	details.value.duration_seconds != null ? `${details.value.duration_seconds.toFixed(2)}s` : "",
)
const exitChip = computed(() =>
	details.value.exit_code != null ? `exit ${details.value.exit_code}` : "",
)
const panelNote = computed(() => {
	if (diffLines.value) {
		const n = details.value.edits
		return n != null ? `${n} edit${n === 1 ? "" : "s"}` : "diff"
	}
	const parts = []
	if (details.value.total_lines != null) parts.push(`${details.value.total_lines} lines`)
	if (details.value.matches != null) parts.push(`${details.value.matches} matches`)
	if (details.value.truncation?.truncated) parts.push("truncated")
	if (details.value.full_output_path) parts.push(`full output: ${details.value.full_output_path}`)
	return parts.join(" · ") || "output"
})

function lineClass(line) {
	if (line.startsWith("+")) return "bg-surface-green-1 text-ink-green-6"
	if (line.startsWith("-")) return "bg-surface-red-1 text-ink-red-6"
	if (line.startsWith("@@")) return "text-ink-gray-4"
	return "text-ink-gray-6"
}
</script>
