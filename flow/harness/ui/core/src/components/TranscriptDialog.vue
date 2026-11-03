<!-- The conversation log: every step's JSON beside its role, with the
     provider's usage under the request that reported it. -->
<template>
	<!-- frappe-ui's Dialog portals where its host keeps overlays (inside an island's shadow root),
	     and brings the overlay, Escape, the focus trap and focus return -->
	<Dialog :open="flow.state.transcriptOpen" size="7xl" @update:open="(open) => open || close()">
		<template #title>
			<div class="flex flex-wrap items-start gap-x-4 gap-y-3 pr-8">
				<div class="min-w-0 flex-1">
					<h2 class="text-2xl-semibold leading-6 text-ink-gray-8">Transcript</h2>
					<div v-if="title" class="mt-1.5 truncate text-base text-ink-gray-6">{{ title }}</div>
				</div>
				<!-- for an issue or another chat: the steps as they show, as JSON -->
				<div v-if="rows.length" class="flex flex-none gap-2">
					<CopyButton :text="json" title="Copy JSON" variant="subtle" size="sm">Copy JSON</CopyButton>
					<Button variant="subtle" size="sm" icon-left="lucide-download" label="Download .json" @click="download" />
				</div>
			</div>
		</template>
		<div class="-mt-2 flex flex-wrap gap-2 border-b border-outline-gray-1 pb-5">
			<div
				v-for="stat in stats"
				:key="stat.label"
				class="min-w-[132px] flex-1 rounded-5 border border-outline-gray-1 px-3.5 py-3"
			>
				<div class="text-xs text-ink-gray-5">{{ stat.label }}</div>
				<div class="mt-2 flex items-baseline gap-1.5">
					<span class="text-base-semibold tabular-nums text-ink-gray-9">{{ stat.value }}</span>
					<span v-if="stat.sub" class="truncate text-xs text-ink-gray-4">{{ stat.sub }}</span>
				</div>
			</div>
		</div>

		<div v-if="!rows.length" class="py-10 text-center text-sm text-ink-gray-5">Nothing sent yet.</div>
		<div
			v-for="row in rows"
			:key="row.key"
			class="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-4 border-b border-outline-gray-1 py-3.5 last:border-0 sm:grid-cols-[5.5rem_minmax(0,1fr)]"
		>
			<span
				class="font-mono text-xs-medium leading-5"
				:class="row.kind === 'error' ? 'text-ink-red-4' : 'text-ink-gray-5'"
				>{{ ROLES[row.kind] }}</span
			>
			<div class="min-w-0 space-y-2 text-sm leading-5">
				<p v-if="row.body" class="max-h-[280px] overflow-auto whitespace-pre-wrap break-words text-ink-gray-8">{{ row.body }}</p>
				<!-- a tool's call and result, and a request's usage, are labelled -->
				<div v-for="part in PARTS.filter((name) => row[name])" :key="part">
					<div v-if="part !== 'entry'" class="mb-1 font-mono text-xs text-ink-gray-4">{{ part }}</div>
					<pre
						class="m-0 max-h-[280px] overflow-auto whitespace-pre-wrap break-words rounded-4 border bg-surface-gray-1 px-3 py-2 font-mono text-xs leading-5 text-ink-gray-6"
						:class="row.kind === 'error' ? 'border-outline-red-2' : 'border-transparent'"
					>{{ JSON.stringify(row[part], null, 2) }}</pre>
				</div>
			</div>
		</div>
	</Dialog>
</template>

<script setup>
import { computed, inject } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Dialog } from "frappe-ui/src/components/Dialog"

import { buildTranscriptRows, formatTokens } from "../transcript.js"
import CopyButton from "./CopyButton.vue"

const ROLES = {
	system: "system",
	user: "user",
	assistant: "assistant",
	tool: "tool",
	compaction: "compact",
	error: "error",
}
// the row's raw objects, in the order they show
const PARTS = ["entry", "input", "output", "usage"]

const flow = inject("flow")

const conversation = computed(() => flow.state.conversation)
const title = computed(() => flow.state.session?.title ?? "")
const rows = computed(() => buildTranscriptRows(conversation.value))

const stats = computed(() => {
	const { usage, requests, subagents, contextTokens, contextWindow } = conversation.value
	// the totals count a sub-agent's usage as this session's, so its calls count too
	const calls = Object.values(subagents ?? {}).reduce((n, child) => n + child.requests.length, requests.length)
	const cached = usage.input ? Math.round((usage.cacheRead / usage.input) * 100) : 0
	const stats = [
		{ label: "Tokens", value: formatTokens(usage.input + usage.output), sub: cached ? `${cached}% cached` : "" },
		{ label: "Input", value: formatTokens(usage.input) },
		{ label: "Output", value: formatTokens(usage.output) },
		{ label: "Model calls", value: String(calls) },
	]
	if (contextTokens) {
		stats.push({
			label: "Context",
			value: formatTokens(contextTokens),
			sub: contextWindow ? `of ${formatTokens(contextWindow)}` : "",
		})
	}
	if (usage.cost) stats.push({ label: "Cost", value: `$${usage.cost.toFixed(usage.cost < 1 ? 3 : 2)}` })
	return stats
})

const json = computed(() =>
	JSON.stringify({ session: flow.state.sessionId, title: title.value, rows: rows.value.map(({ key, ...row }) => row) }, null, 2),
)

function download() {
	const url = URL.createObjectURL(new Blob([json.value], { type: "application/json" }))
	const link = Object.assign(document.createElement("a"), { href: url, download: `transcript-${flow.state.sessionId ?? "chat"}.json` })
	link.click()
	setTimeout(() => URL.revokeObjectURL(url))
}

function close() {
	flow.setTranscriptOpen(false)
}
</script>
