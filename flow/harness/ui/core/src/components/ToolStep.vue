<template>
	<div>
		<component
			:is="expandable ? 'button' : 'div'"
			class="flex w-full items-baseline gap-2.5 py-2.5 text-left"
			:class="[expandable ? 'group cursor-pointer' : '', live ? 'flow-tool-live' : '']"
			@click="expandable && (open = !open)"
		>
			<!-- leading slot doubles as the disclosure control: the tool icon yields
			     to a chevron on hover, and to the rotated (close) chevron while open -->
			<span class="relative h-3.5 w-3.5 flex-none self-center text-ink-gray-5">
				<FeatherIcon
					:name="icon"
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : expandable ? 'group-hover:opacity-0' : ''"
				/>
				<FeatherIcon
					v-if="expandable"
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
			<!-- a call the user denied, cancelled, or redirected -->
			<div v-if="decision" class="px-3 py-2.5">
				<div class="text-xs font-medium" :class="statClass">{{ decisionTitle }}</div>
				<div v-if="decision.user_feedback" class="mt-1 text-xs leading-relaxed text-ink-gray-6">
					“{{ decision.user_feedback }}”
				</div>
			</div>

			<template v-else>
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
					class="m-0 max-h-[260px] overflow-auto py-2 font-mono text-xs leading-[1.7]"
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

import { compactDisplayText, stepDecision, stepIcon, stepLabel, stepStat, stepSubject } from "../transcript.js"
import CopyButton from "./CopyButton.vue"

const props = defineProps({
	step: { type: Object, required: true },
	// this step is the one executing right now — its row carries the sweep
	live: { type: Boolean, default: false },
})

const open = ref(false)

const flow = inject("flow", null)
const cwd = computed(() => flow?.state?.session?.config?.cwd ?? null)

const displaySegments = computed(() =>
	(props.step.call.display ?? []).map((segment) =>
		segment.arg ? { ...segment, text: compactDisplayText(segment.text, cwd.value) } : segment,
	),
)

// a host describes its own tools; the daemon's have display segments or defaults
const meta = computed(() => {
	const call = props.step.call
	return flow?.options?.presentTool?.(call.name, call.arguments ?? call.args ?? {}) ?? {}
})
const icon = computed(() => meta.value.icon ?? stepIcon(props.step.call.name))
const label = computed(() => meta.value.label ?? stepLabel(props.step.call.name))
const subject = computed(() =>
	compactDisplayText(meta.value.subject ?? stepSubject(props.step.call), cwd.value),
)
const failed = computed(() => props.step.result?.is_error === true)
const details = computed(() => props.step.result?.details ?? {})
const output = computed(() => props.step.result?.content ?? "")

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
	return stepStat(props.step)
})
const statClass = computed(() => {
	if (decision.value) return decision.value.status === "redirect" ? "text-ink-amber-6" : "text-ink-red-6"
	return failed.value ? "text-ink-red-6" : "text-ink-gray-4"
})

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
// point (command output, search hits, diffs, custom tool results) or the user intervened
// expanding near the bottom edge would reveal the payload off-screen;
// nudge it into view (no-op when it is already visible)
const payloadEl = ref(null)
watch(payloadEl, (el) => el?.scrollIntoView({ block: "nearest", behavior: "smooth" }))

const expandable = computed(() => {
	if (!props.step.result) return false
	if (decision.value) return true
	if (diffLines.value) return true
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
